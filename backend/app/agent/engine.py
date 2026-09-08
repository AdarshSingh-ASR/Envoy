"""The NegotiationEngine: drives advocate vs. provider, round by round.

Quiet by design: the only points where the human is pulled in are
  - intent=consult_owner from Envoy (a genuine judgment call), and
  - a settlement candidate (money leaves the owner's life either way).
Those become Decision Cards; the runner thread blocks until the owner answers
(or times out), then continues exactly where it stopped.
"""
from __future__ import annotations

import threading
import time
import traceback
from typing import Any

from .. import store
from ..scenarios import SCENARIOS  # noqa: F401 - re-exported for _run_locked
from .advocate import negotiator_agent, negotiator_move, run_strategy_graph
from .protocol import Move, Offer, offer_value
from .provider import provider_move

MAX_ROUNDS = 6
CONSULT_TIMEOUT_S = 3600
DECISION_TIMEOUT_S = 3600
PACE_S = 20  # stay inside free-tier tokens-per-minute windows

_running: set[str] = set()
_lock = threading.Lock()
_sem = threading.BoundedSemaphore(1)  # free-tier TPM: negotiate one at a time


def start_negotiation(nid: str) -> None:
    with _lock:
        if nid in _running:
            return
        _running.add(nid)
    threading.Thread(target=_run, args=(nid,), daemon=True).start()


def _run(nid: str) -> None:
    try:
        with _sem:
            _run_locked(nid)
    except Exception as exc:  # noqa: BLE001
        store.update_negotiation(nid, status="failed")
        store.add_turn(nid, "system", "error", f"Engine failure: {exc}")
        traceback.print_exc()
    finally:
        with _lock:
            _running.discard(nid)


def _run_locked(nid: str) -> None:
    neg = store.get_negotiation(nid)
    if not neg:
        return
    from ..scenarios import GENERIC_SCENARIO, infer_scenario

    scenario_id = neg["scenario_id"] or infer_scenario(neg["raw_text"])
    if scenario_id not in SCENARIOS:
        scenario_id = "generic"
    store.update_negotiation(nid, scenario_id=scenario_id)

    store.update_negotiation(nid, status="working")
    store.add_turn(nid, "system", "phase", "Building your case: intake - research - strategy")

    strategy_text, research_text = run_strategy_graph(neg)
    store.update_negotiation(nid, strategy=strategy_text)
    store.add_turn(nid, "system", "phase", "Strategy locked. Opening negotiation with "
                   f"{SCENARIOS[scenario_id]['provider_name']}'s agent.")

    agent = negotiator_agent(nid, strategy_text, research_text)

    mv: Move | None = None
    for round_no in range(MAX_ROUNDS):
        transcript = _transcript_text(nid, last=10)

        # --- advocate turn -------------------------------------------
        time.sleep(PACE_S)
        if mv is None:
            mv = negotiator_move(agent, transcript, round_no, MAX_ROUNDS)
        store.add_turn(nid, "advocate", mv.intent, mv.message,
                       mv.offer.model_dump() if mv.offer else None)

        if mv.intent == "accept":
            _settle(nid, scenario_id, mv.offer, transcript, accepted_by="advocate")
            return
        if mv.intent == "consult_owner":
            answer = _consult(nid, mv.owner_question or "Envoy needs your call.")
            if answer is None:
                store.update_negotiation(nid, status="failed", outcome="consult timed out")
                return
            store.add_turn(nid, "system", "owner_instruction", f"Owner says: {answer}")
            time.sleep(PACE_S)
            mv = negotiator_move(
                agent,
                _transcript_text(nid, last=10),
                round_no,
                MAX_ROUNDS,
            )
            continue  # record the fresh advocate move next iteration

        # --- provider turn -------------------------------------------
        time.sleep(PACE_S)
        pmv = provider_move(scenario_id, round_no, _transcript_text(nid, last=8))
        store.add_turn(nid, "provider", pmv.intent, pmv.message,
                       pmv.offer.model_dump() if pmv.offer else None)

        if pmv.intent == "accept":
            _settle(nid, scenario_id, pmv.offer, _transcript_text(nid, last=10),
                    accepted_by="provider")
            return
        mv = None  # advocate moves next round

    # ---- Impasse review: the one real decision Envoy escalates --------
    last_provider = next(
        (t for t in reversed(store.list_turns(nid))
         if t["side"] == "provider" and t["offer"] and t["offer"]["kind"] != "none"),
        None,
    )
    if last_provider:
        from .protocol import Offer, describe_offer

        best = Offer(**last_provider["offer"])
        summary = describe_offer(best)
        question = (
            f"Impasse with {SCENARIOS[scenario_id]['provider_name']}: Envoy hit its ceiling "
            f"and their final position is: {summary}. Accept their best offer, or decline "
            "and Envoy hands you the escalation pack (chargeback / regulator / switch)."
        )
        did = store.create_decision(
            nid, "impasse_review", question,
            {"offer": best.model_dump(), "summary": summary},
        )
        answer = _wait_answer(nid, did, DECISION_TIMEOUT_S)
        if answer == "approved":
            store.record_settlement(nid, offer_value(best), best.currency or "INR",
                                    f"Impasse settlement: {summary}")
            return
        store.update_negotiation(nid, status="declined",
                                 outcome="Owner chose escalation over their best offer")
        store.add_turn(nid, "system", "declined",
                       "Owner declined their best offer. Escalation pack: every artifact from "
                       "this negotiation is kept as evidence.")
        return

    store.update_negotiation(nid, status="impasse", outcome="No settlement within round limit")
    store.add_turn(nid, "system", "impasse",
                   "Negotiation closed without settlement. Escalation paths are on the record.")


# ------------------------------------------------------------------ helpers --

def _transcript_text(nid: str, last: int = 8) -> str:
    turns = store.list_turns(nid)[-last:]
    lines = []
    for t in turns:
        offer = ""
        if t["offer"]:
            o = t["offer"]
            offer = f" | offer={o['kind']} amount={o.get('amount', 0)} {o.get('currency', '')} months={o.get('months', 0)} cond={o.get('conditions', '')}"
        msg = t["message"][:280]
        lines.append(f"{t['side'].upper()} ({t['intent']}): {msg}{offer}")
    return "\n".join(lines)


def _consult(nid: str, question: str) -> str | None:
    did = store.create_decision(nid, "consult", question, {})
    return _wait_answer(nid, did, CONSULT_TIMEOUT_S)


def _wait_answer(nid: str, did: str, timeout_s: float) -> str | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        d = store.get_decision(did)
        if d and d["status"] in {"approved", "declined"}:
            return d["status"]
        time.sleep(1.0)
    return None


def _settle(nid: str, scenario_id: str, offer: Offer, transcript: str, accepted_by: str) -> None:
    """Settle on the accepted offer directly (it already came from a side that
    was authorized to make it), then ask the owner once."""
    from .protocol import describe_offer

    value = offer_value(offer)
    summary = describe_offer(offer)
    question = (
        f"Settlement reached with {SCENARIOS[scenario_id]['provider_name']}: "
        f"{summary} - approve?"
    )
    did = store.create_decision(
        nid, "settlement_approval", question,
        {"offer": offer.model_dump(), "summary": summary, "accepted_by": accepted_by},
    )
    answer = _wait_answer(nid, did, DECISION_TIMEOUT_S)

    if answer == "approved":
        store.record_settlement(nid, value, offer.currency or "INR", summary)
    else:
        store.update_negotiation(nid, status="declined", outcome="Owner declined settlement")
        store.add_turn(nid, "system", "declined",
                       "Owner declined. Negotiation closed; escalation path noted.")


