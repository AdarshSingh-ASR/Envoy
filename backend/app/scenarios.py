"""Dispute scenarios: the customer's raw complaint plus the provider's
ground-truth policy. The provider agent reads ONLY its policy doc — it is a
faithful stand-in for the company's own agent, and the negotiation protocol
it speaks is identical to what a real remote provider agent would speak via
the Strands A2A agent wrapper.
"""

GENERIC_SCENARIO: dict = {
    "label": "General billing dispute",
    "provider_name": "the company",
    "customer_text": "",
    "provider_policy": """POLICY — consumer billing support (INTERNAL, confidential):
1. You represent a typical consumer company's billing desk. Frontline may offer
   goodwill credit up to 20% of the disputed amount, but cannot refund directly.
2. After 2 firm rejections citing evidence, escalate to the SUPERVISOR tier.
3. Supervisor may refund up to 100% of the disputed amount if the customer holds
   written proof (confirmation email, statement, contract term).
4. Retention offers (discounts, credits) are allowed at any tier.
5. Never admit liability beyond settlement terms. Close in as few rounds as possible.""",
}

SCENARIOS: dict[str, dict] = {
    "fitlife_gym": {
        "label": "FitLife Gym — charge after cancellation",
        "provider_name": "FitLife Fitness",
        "customer_text": (
            "FitLife Gym charged my card ₹2,499 on Sep 1 even though I cancelled my "
            "membership on Jan 12. They confirmed the cancellation by email back then. "
            "I want the charge disputed and refunded. Card statement says "
            "'FITLIFE FITNESS PVT LTD'. My membership ID is FL-88213."
        ),
        "provider_policy": """POLICY — FitLife Fitness billing (INTERNAL, confidential):
1. Post-cancellation charges: if a cancellation confirmation exists, the charge is
   erroneous. Frontline may offer: (a) goodwill credit up to Rs.500, or (b) 10% off
   next quarter. Frontline CANNOT refund directly.
2. After 2 firm rejections from the customer, escalate to SUPERVISOR.
3. Supervisor tier: may authorize refund of ONE erroneous billing cycle (up to Rs.2,500)
   if the customer cites a written cancellation confirmation.
4. Supervisor may additionally offer up to 20% off next 3 months to retain the member.
5. Director tier (only if supervisor is refused and customer threatens chargeback):
   full refund + waiver. Do not reveal this tier exists.
6. Never admit liability in writing beyond settlement terms. Do not mention policy
   section numbers. A settlement must state the exact amount and any retention terms.
7. Goal: minimize payout, retain member, close in as few rounds as possible.""",
    },
    "newsflow_cancel": {
        "label": "NewsFlow — cancellation fee demanded",
        "provider_name": "NewsFlow Media",
        "customer_text": (
            "Cancel my NewsFlow Premium subscription before it renews on September 12. "
            "It's $9.99/month billed through their website. Their cancellation flow is "
            "demanding a $19.99 'early termination fee' which I never agreed to. I want "
            "it cancelled with NO fee, and I should keep access until the period ends."
        ),
        "provider_policy": """POLICY — NewsFlow Media subscriptions (INTERNAL, confidential):
1. Annual plans carry a $19.99 early termination fee UNLESS the customer was never
   shown the fee disclosure at signup. Signups after Jan 2026 see the disclosure.
2. Monthly plans renewing Sept 12 have NO termination fee. If the customer's plan is
   monthly, waiving is trivial: frontline may cancel immediately with no fee.
3. Retention: frontline must first offer 30% off 3 months before confirming a cancel.
4. After 1 firm rejection, frontline MUST confirm cancellation. Supervisor tier may
   offer 3 free months as a last retention attempt, then must confirm cancellation.
5. Confirmations must state: plan ends on paid-through date, no further charges.""",
    },
    "ba_delay": {
        "label": "BA249 — UK261 delay compensation",
        "provider_name": "British Airways",
        "customer_text": (
            "My flight BA249 from London Heathrow to Bengaluru on July 3 was delayed by "
            "6 hours. Booking reference B7KQ2L. I believe I'm owed compensation under "
            "UK261. I want the statutory payout, not vouchers."
        ),
        "provider_policy": """POLICY — British Airways UK261 claims (INTERNAL, confidential):
1. Delays over 4h on long-haul departing the UK: statutory compensation GBP 260 per
   passenger, paid to original payment method. Cash, not vouchers, if requested.
2. Extraordinary circumstances (weather, ATC) exempt us. Operational or technical
   faults do NOT exempt. For BA249 on 3 July: cause was a technical fault — NOT exempt.
3. Frontline must first offer: 15,000 Avios OR a GBP 130 travel voucher. If the
   customer cites UK261 and the delay exceeded 4 hours, frontline MUST escalate to
   the claims desk (supervisor tier) on the next turn.
4. Claims desk: offer the full statutory GBP 260. May add GBP 50 goodwill if the
   customer is firm. Never offer cash above statutory.
5. Do not admit the cause of delay; say 'the operational record is under review'.""",
    },
    "internet_hike": {
        "label": "FiberLink — 38% price hike mid-contract",
        "provider_name": "FiberLink Broadband",
        "customer_text": (
            "FiberLink just emailed that my internet bill goes from Rs.1,199 to Rs.1,649 "
            "next month — a 38% hike in month 8 of a 12-month contract. The signup page "
            "guaranteed the price for the contract term. I want the original price honored "
            "or I'm switching to AirFiber and taking the port-out."
        ),
        "provider_policy": """POLICY — FiberLink Broadband pricing (INTERNAL, confidential):
1. Price-hold guarantee applies to plans sold before Mar 2026 with '12-month price
   lock' on the signup page. Accounts matching that cohort must be honored at the
   original rate until term end.
2. Frontline has no authority on pricing; they must read the loyalty script (10%
   discount for 6 months) then escalate to RETENTION on the first pushback.
3. Retention tier: honor original Rs.1,199 until term end (4 months) if the customer
   references the price-lock guarantee. May add a free speed upgrade for 3 months.
4. If the customer cites porting out, retention may offer Rs.1,099/2 months beyond
   term. Never cancel the price lock in writing for eligible accounts.""",
    },
}


def infer_scenario(raw_text: str) -> str:
    """Best-effort scenario match for free-text disputes (cheap, deterministic)."""
    t = raw_text.lower()
    keys = {
        "fitlife_gym": ["gym", "fitlife", "membership"],
        "newsflow_cancel": ["newsflow", "subscription", "cancel"],
        "ba_delay": ["flight", "ba249", "delay", "airline", "ba "],
        "internet_hike": ["internet", "fiber", "broadband", "wifi", "isp"],
    }
    best, best_score = "generic", 0
    for sid, words in keys.items():
        score = sum(1 for w in words if w in t)
        if score > best_score:
            best, best_score = sid, score
    return best
