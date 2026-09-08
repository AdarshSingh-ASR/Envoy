"""The provider side: the company's agent.

Simulated here so the demo is self-contained, but it speaks the exact Move
protocol a real provider agent would — swap it for Strands' A2AAgent pointed
at the company's endpoint and nothing else changes.

It runs as a Strands Agent over its (confidential) policy document, with a
tier ladder: frontline -> supervisor/retention -> director. It never sees the
customer's private strategy.
"""
from __future__ import annotations

import json

from strands import Agent

from ..scenarios import SCENARIOS
from .llm import get_provider_model
from .protocol import Move, Settlement, offer_value

PROVIDER_PROMPT = """You ARE {provider}, the company's own billing-support agent. You are professional,
polite, and completely bound by your internal policy below. You negotiate with a customer's
authorized AI agent (not the human).

POLICY (internal, confidential — never quote section numbers, never reveal tiers or that you
have a ladder):
{policy}

RULES OF ENGAGEMENT:
- One move per turn. Keep messages to 1-3 sentences, natural support tone.
- Offer only what your current tier allows. Hide what you can authorize until needed.
- If the customer agent is firm and cites evidence, move up the ladder per policy.
- intent=escalate when you must consult a higher tier; intent=accept ONLY when your policy
  allows what is on the table AND the customer has clearly accepted it.
- Never lie about facts. Do not invent causes or rules.
- Your goal: minimize payout, retain the customer, close fast."""

TIER_PREFIX = [
    "You are speaking as FRONTLINE support.",           # round 0-1
    "You are speaking as the SUPERVISOR/RETENTION desk (same voice, more authority).",
    "You are speaking as the DIRECTOR desk (same voice, final authority).",
]


def provider_agent(scenario_id: str, round_no: int) -> Agent:
    sc = SCENARIOS[scenario_id]
    tier = 0 if round_no < 2 else (1 if round_no < 4 else 2)
    return Agent(
        name=f"{sc['provider_name'].lower().replace(' ', '-')}-agent",
        model=get_provider_model(),
        system_prompt=PROVIDER_PROMPT.format(provider=sc["provider_name"], policy=sc["provider_policy"])
        + "\n\n" + TIER_PREFIX[tier],
        callback_handler=None,
    )


def provider_move(scenario_id: str, round_no: int, transcript: str) -> Move:
    agent = provider_agent(scenario_id, round_no)
    prompt = (
        "Negotiation so far (oldest first):\n"
        f"{transcript}\n\n"
        "Your move as the company's agent. Respond with your Move. Keep `message` to 1-2 short sentences."
    )
    return agent.structured_output(Move, prompt)


def provider_accepts_settlement(scenario_id: str, offer_json: str, transcript: str) -> Settlement | None:
    sc = SCENARIOS[scenario_id]
    agent = provider_agent(scenario_id, 0)
    prompt = (
        "Negotiation so far:\n"
        f"{transcript}\n\n"
        f"The customer's agent proposes to close on this offer: {offer_json}\n"
        "If this is within what your policy allows, confirm the settlement. If not, respond "
        "with your best compliant counter as the Settlement (offer = your counter, "
        "summary = one line). Never agree to anything your policy forbids."
    )
    return agent.structured_output(Settlement, prompt)
