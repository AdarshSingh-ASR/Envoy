# Envoy architecture

## Components

```
backend/app/
  main.py                 FastAPI: disputes in, negotiations out, decisions answered
  store.py                SQLite: negotiations, transcript turns, decisions, settlements, ledger
  scenarios.py            dispute scenarios + confidential provider policies + inference
  agent/
    protocol.py           the shared Move/Offer/Settlement contract (A2A-compatible)
    advocate.py           Envoy: strategy Graph (intake->research->strategy) + negotiator agent
    provider.py           the company's agent: policy-bound, tiered authority (frontline/supervisor/director)
    engine.py             negotiation loop: rounds, termination, Decision Cards, settlements, ledger
    llm.py                LiteLLM providers (advocate 120b / provider 20b, any vendor via env)
    research.py           Tavily-backed web search tool
  config.py               env-driven configuration

frontend/src/App.tsx      Negotiation Room: live transcript, offer chips, Decision Cards, savings ledger
```

## Runtime flow

1. **Dispute intake.** `POST /api/negotiations` stores the raw text. A runner thread starts (one at a time — friendly to free-tier rate limits).
2. **Strategy graph.** A Strands `Graph` (intake → research → strategy) classifies the dispute, pulls Tavily snippets, and produces the private strategy: opening ask, reserve (walk-away), BATNA, tactics. Web results are injected into the task so each node is one LLM call.
3. **Negotiation loop.** Round by round:
   - advocate produces a typed `Move` (session-managed agent; conversation persists across restarts)
   - provider produces a `Move` under its tier authority — it escalates internally when the customer is firm, and *never* sees the advocate's strategy
   - termination: either side `accept`s, or the round limit hits
4. **Human gate.** On settlement candidate → `settlement_approval` Decision Card; on impasse → `impasse_review` card with the provider's best offer. The runner thread blocks until the owner answers (UI → `POST /api/decisions/{id}/respond`), then continues exactly where it stopped.
5. **Settlement.** Approved settlements are recorded with a reference ID into the savings ledger; declines close the negotiation with an escalation pack.

## Why two models

Groq's free tier rate-limits **per model**, so the advocate (gpt-oss-120b) and the provider (gpt-oss-20b) each get an independent token bucket. It also reads honestly: the two parties genuinely run different weights.

## Rate-limit engineering

- `num_retries=10` with LiteLLM backoff
- engine paces LLM calls (`PACE_S`) between rounds
- strategy-graph nodes are single-call by design (web snippets injected, not tool-looped)
- negotiation transcripts are windowed (last 8 turns, truncated)

## Swapping in a real provider agent

The `Move` schema is the whole contract. Replace `provider.provider_move()` with a Strands `A2AAgent` pointed at the company's endpoint; the engine, UI, and decision flow are unchanged. That is the product thesis: when companies expose their support agents, customers get an equal seat.
