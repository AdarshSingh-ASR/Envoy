"""The advocate side: Envoy, the customer's agent.

Phase A (Strands Graph): intake -> research -> strategy. Produces a private
strategy: claim value, reserve (walk-away), opening ask, BATNA, tactics.

Phase B: the negotiator agent works round-by-round inside the engine loop,
guarded by the ConsultGate hook — when it is about to accept a settlement
below its reserve, or when it genuinely needs the human, it raises a Strands
interrupt that becomes a Decision Card. Everything else is quiet.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from strands import Agent
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands.multiagent import GraphBuilder
from strands.models.litellm import LiteLLMModel
from strands.session.file_session_manager import FileSessionManager

from ..config import OWNER_PROFILE, SESSIONS_DIR
from .llm import get_model
from .protocol import Move
from .research import web_search

OWNER = f"{OWNER_PROFILE['name']} <{OWNER_PROFILE['email']}>"


# ----------------------------------------------------------- structured out --

class Triage(BaseModel):
    category: str = Field(description="one of: billing_dispute, refund_claim, cancellation, price_increase, compensation")
    counterparty: str = Field(description="company name")
    claim_value: float = Field(description="monetary value at stake, in the currency")
    currency: str
    evidence: list[str] = Field(description="facts, references, dates from the complaint that support the customer")


class Strategy(BaseModel):
    opening_ask: str = Field(description="what to demand in the opening move")
    reserve: str = Field(description="walk-away line: minimum acceptable outcome")
    batna: str = Field(description="best alternative if negotiation fails (chargeback, regulator, switch)")
    tactics: list[str] = Field(description="3-5 concrete tactics for this negotiation")
    tone: str = Field(description="how to sound: firm-but-polite, escalation-ready, etc.")


# ------------------------------------------------------------- graph (A) ----

RESEARCH_PROMPT = """You are Envoy's research agent. From the dispute and the gathered snippets, state
the customer's strongest lever (written proof, regulation, policy norm), the realistic settlement
range for such cases, and the owner's alternatives if this fails. Be concrete and brief. Owner: """ + OWNER

TRIAGE_PROMPT = """You are Envoy's intake agent. Classify the dispute: category, counterparty, the money
at stake, and the evidence the customer holds. Owner: """ + OWNER

STRATEGY_PROMPT = """You are Envoy's strategy agent. From the intake and research, set the negotiation
plan: an ambitious-but-credible opening ask, the reserve (walk-away), the BATNA, and concrete tactics.
Your ENTIRE answer must be under 150 words. No tables, no headings, no timelines.
Owner: """ + OWNER


def run_strategy_graph(neg: dict[str, Any]) -> tuple[str, str]:
    """Runs intake -> research -> strategy as a Strands Graph.
    Returns (strategy_json_text, research_text). Web results are fetched by
    the engine and injected into the task so every node is one LLM call."""
    triage = Agent(name="intake", model=get_model(), system_prompt=TRIAGE_PROMPT, callback_handler=None)
    research = Agent(name="research", model=get_model(), system_prompt=RESEARCH_PROMPT,
                     callback_handler=None)
    strategy = Agent(name="strategy", model=get_model(), system_prompt=STRATEGY_PROMPT, callback_handler=None)

    builder = GraphBuilder()
    builder.add_node(triage, "intake")
    builder.add_node(research, "research")
    builder.add_node(strategy, "strategy")
    builder.add_edge("intake", "research")
    builder.add_edge("research", "strategy")
    builder.set_entry_point("intake")
    builder.set_execution_timeout(600)
    builder.set_max_node_executions(10)
    graph = builder.build()

    snippets = _research_snippets(neg["raw_text"])
    task = (
        f"DISPUTE: {neg['raw_text']}\n\n"
        f"WEB RESEARCH SNIPPETS:\n{snippets}\n\n"
        "Classify the dispute, state the leverage, then set the strategy."
    )
    result = graph(task)

    research_text, strategy_text = "", ""
    for node in result.execution_order:
        text = str(node.result.result)
        if node.node_id == "research":
            research_text = text
        elif node.node_id == "strategy":
            strategy_text = text
    return strategy_text, research_text


def _research_snippets(raw_text: str) -> str:
    try:
        from .research import web_search
        return str(web_search(raw_text[:300]))[:1200]
    except Exception:  # noqa: BLE001 - search is optional
        return "(web search unavailable; rely on general knowledge)"


# ------------------------------------------------------- negotiator (B) -----

NEGOTIATOR_PROMPT = """You are Envoy, {owner}'s negotiating agent. You negotiate so your owner never
has to. You are firm, evidence-driven, and professional — never rude, never bluffing.

YOUR PRIVATE STRATEGY (the counterparty must never see this):
{strategy}

RESEARCH:
{research}

PROTOCOL:
- One Move per turn. 1-3 sentences in message. In character.
- intent: open (first demand) / counter / firm (restate demand with evidence) / accept (their
  offer meets the reserve) / escalate (demand their supervisor) / final (take it or leave it) /
  consult_owner (you genuinely need your human — set owner_question).
- consult_owner ONLY when: accepting would betray the reserve, the counterparty is stonewalling
  and you need a real decision, or the situation is ambiguous. This pings your owner — use sparingly.
- accept ONLY when their offer is at or above your reserve line.
- Track what they've offered across turns; concede slowly; anchor high at open."""

CONSULT_REVIEW_PROMPT = """You are Envoy's judgment layer. Your negotiator wants to consult the owner.
If the consult is unnecessary (the answer follows from the strategy or is a routine call), answer it
yourself and continue negotiating — the owner should only be pinged for real decisions. Respond with
JSON: {{"handle_yourself": true/false, "answer_if_trivial": "...", "reason": "..."}}"""


def negotiator_agent(nid: str, strategy: str, research: str, resume: bool = False) -> Agent:
    return Agent(
        name="envoy-negotiator",
        model=get_model(),
        system_prompt=NEGOTIATOR_PROMPT.format(owner=OWNER, strategy=strategy, research=research),
        session_manager=FileSessionManager(
            session_id=f"neg-{nid}", storage_dir=str(SESSIONS_DIR)
        ),
        callback_handler=None,
    )


def negotiator_move(agent: Agent, transcript: str, round_no: int, max_rounds: int) -> Move:
    prompt = (
        f"Negotiation so far (oldest first), round {round_no + 1} of max {max_rounds}:\n"
        f"{transcript}\n\nYour move. Respond with your Move."
    )
    return agent.structured_output(Move, prompt)
