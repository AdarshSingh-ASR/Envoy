"""Negotiation protocol: shared structured vocabulary both sides speak.

The provider simulator and (in production) a real remote provider agent
exchange these exact Move objects — so swapping the simulator for a live
counterparty via Strands' A2AAgent is a drop-in change.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Offer(BaseModel):
    kind: str = Field(
        description="one of: full_refund, partial_refund, credit, discount_months, fee_waiver, voucher, price_lock, none"
    )
    amount: float = Field(
        default=0.0,
        description="monetary value in `currency` units. For discount_months put the PERCENT here (e.g. 30). For fee_waiver put the waived fee. Otherwise 0."
    )
    currency: str = Field(default="INR")
    months: int = Field(default=0, description="months for discount/credit/price-lock terms")
    conditions: str = Field(default="", description="binding conditions attached")


class Move(BaseModel):
    """One turn in the negotiation protocol."""
    intent: str = Field(
        description="one of: open, counter, firm, accept, escalate, consult_owner, final"
    )
    offer: Offer
    message: str = Field(description="1-3 sentences, in character, no policy leaks")
    owner_question: str = Field(
        default="", description="ONLY when intent=consult_owner: the one-line question for the human"
    )


class Settlement(BaseModel):
    """The structured contract both sides accept."""
    offer: Offer
    summary: str = Field(description="one line: exactly what is being agreed")


def offer_value(o: Offer) -> float:
    """Cash-equivalent value of an offer for the savings ledger."""
    if o.kind in {"full_refund", "partial_refund", "credit", "voucher"}:
        return float(o.amount or 0)
    return 0.0  # discounts/waivers are real wins but not cash


def describe_offer(o: Offer) -> str:
    """Human summary of an offer, robust to where the model put the number."""
    import re

    if o.kind == "full_refund":
        return f"Full refund of {o.currency} {o.amount:,.0f}" if o.amount else "Full refund"
    if o.kind == "partial_refund":
        return f"Partial refund of {o.currency} {o.amount:,.0f}"
    if o.kind == "credit":
        return f"Account credit of {o.currency} {o.amount:,.0f}"
    if o.kind == "voucher":
        return f"Voucher worth {o.currency} {o.amount:,.0f}"
    if o.kind == "fee_waiver":
        fee = f" of {o.currency} {o.amount:,.0f}" if o.amount else ""
        return f"Fee{fee} waived"
    if o.kind == "discount_months":
        pct = o.amount
        if not pct:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", o.conditions or "")
            pct = float(m.group(1)) if m else 0
        return f"{pct:.0f}% off for {o.months} months"
    if o.kind == "price_lock":
        return f"Original price locked for {o.months} months"
    return o.conditions or "Terms agreed"
