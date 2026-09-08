# Envoy

**Your negotiating agent.** Companies deployed AI agents to talk to you — support bots, billing bots, retention bots. Customers walk into those negotiations unarmed. Envoy is your seat at the table.

Envoy is an autonomous consumer-advocacy agent built with the [Strands Agents SDK](https://github.com/strands-agents). Hand it a billing dispute, a refund claim, a cancellation fight, or a price hike. Envoy builds the case (intake → research → strategy as a Strands **multi-agent Graph**), then negotiates **live against the company's own agent** — a second, independent Strands agent bound by the company's internal policy with a frontline → supervisor → director authority ladder — while you do nothing.

You see exactly one thing: a **Decision Card** when there's a real decision to make (a settlement, or an impasse where you choose between their best offer and escalation). Everything else is quiet.

---

## The problem

Disputing a charge is one of the most repetitive, judgment-heavy chores in life: hold music, re-explaining, being offered vouchers, repeating yourself, giving up. Companies automated their side of this conversation. Envoy automates yours — and keeps a human only where the human matters: **the decision to accept money.**

## How it works

```
you ──▶ dispute (paste text / forward email)
          │
          ▼
   ┌───────────────────────────────┐
   │  STRATEGY GRAPH (Strands)     │   intake ─▶ research ─▶ strategy
   │  claim value · reserve · BATNA│   (web research with Tavily when available)
   └──────────────┬────────────────┘
                  ▼
   ┌───────────────────────────────┐        ┌────────────────────────────┐
   │  ENVOY (advocate agent)       │◀──────▶│  COMPANY AGENT (provider)  │
   │  firm, evidence-driven,       │ Move   │  bound by internal policy, │
   │  knows your reserve & BATNA   │ schema │  frontline→supervisor→     │
   └──────────────┬────────────────┘        │  director authority ladder │
                  │                          └────────────────────────────┘
                  ▼
        settlement or impasse?
                  │
                  ▼
        ┌──────────────────┐
        │  DECISION CARD   │  ◀── the only time you're interrupted
        │  [Approve] [✗]   │
        └────────┬─────────┘
                 ▼
     settlement executed → savings ledger
```

### What's inside (Strands features used)

| Strands capability | Where |
| --- | --- |
| **Multi-agent Graph** (`GraphBuilder`, deterministic DAG) | strategy phase: intake → research → strategy |
| **Two independent agents** negotiating | advocate (`gpt-oss-120b`) vs. provider (`gpt-oss-20b`) — split across models also keeps each on its own free-tier rate bucket |
| **Structured output** (Pydantic) | every negotiation turn is a typed `Move` (intent + offer + message); settlements are typed contracts |
| **Session persistence** (`FileSessionManager`) | each negotiation is a resumable session; interrupted negotiations survive restarts |
| **LiteLLM model provider** | any provider works — Groq / OpenRouter / Gemini / Bedrock — via one env var |
| **Web research tool** (`@tool`) | Tavily-backed research injected into the strategy phase; degrades gracefully offline |
| **A2A-compatible protocol** | both sides speak the same `Move` schema, so the simulated provider can be swapped for a real remote provider agent via Strands' `A2AAgent` without changing the engine |

### The negotiation protocol

Each turn is a structured `Move`:

- `intent`: `open | counter | firm | accept | escalate | final | consult_owner`
- `offer`: typed (`full_refund`, `partial_refund`, `credit`, `discount_months`, `fee_waiver`, `voucher`, `price_lock`) with amount, currency, months, and binding conditions
- `message`: 1–3 sentences in character

The engine enforces round limits, routes every offer through the counterpart's policy authority, and surfaces exactly two kinds of Decision Cards:

1. **Settlement approval** — money moves only if you tap Approve.
2. **Impasse review** — Envoy hit its ceiling: take their best offer, or decline and get an escalation pack (chargeback / regulator / switch) with the full negotiation as evidence.

## Run it

```bash
# backend (Python 3.12+)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env          # set ENVOY_MODEL + a provider key (see below)

.venv/Scripts/python -m uvicorn app.main:app --port 8000

# frontend (Node 20+)
cd ../frontend
npm install
npm run dev                   # http://localhost:5173
```

### Model configuration (any one)

```env
ENVOY_MODEL=groq/openai/gpt-oss-120b              + GROQ_API_KEY=...
ENVOY_MODEL=openrouter/anthropic/claude-sonnet-4.5 + OPENROUTER_API_KEY=...
ENVOY_MODEL=gemini/gemini-3.6-flash                + GEMINI_API_KEY=...
ENVOY_MODEL=bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0  + AWS creds
```

The provider side defaults to `groq/openai/gpt-oss-20b` (override with `ENVOY_PROVIDER_MODEL`). Groq rate-limits per model, so the two parties run on separate buckets.

### Demo disputes included

Four seeded scenarios, each with a realistic confidential provider policy the company agent must obey: a gym charge after cancellation, a subscription cancellation fee, a UK261 flight-delay claim, and a mid-contract price hike. Or paste any dispute as free text — Envoy infers the scenario class and falls back to a generic consumer-policy agent.

## What a run looks like

1. Paste: *"FitLife Gym charged my card ₹2,499 on Sep 1 even though I cancelled in January…"*
2. Envoy's strategy graph classifies it, researches leverage, sets reserve = full refund, BATNA = chargeback.
3. Envoy opens hard. The company's frontline offers 10% off next quarter. Envoy holds firm, cites the written cancellation.
4. The company escalates internally; its supervisor-tier authorizes the refund.
5. Your phone buzzes once: **Decision Card — "Settlement: full refund of ₹2,499. Approve?"**
6. You tap Approve. The savings ledger ticks up. You never spoke to anyone.

## Honest scope notes

- The **provider agent is a faithful simulator** of the company's agent: it reads only its (fictional but realistic) policy document and speaks the same protocol a real remote agent would. Swapping in a live counterparty is an `A2AAgent` wrapper away.
- "Settlement executed" writes a verifiable artifact (reference ID, terms) into the app's ledger; it does not move real money. All negotiation behavior — strategy, tactics, offers, acceptances, impasses — is real agent behavior, not scripted.

## Roadmap

- Email-forward ingestion (`fwd@envoy.app`) and payment-provider webhooks
- Real provider integrations over A2A as companies open their agents
- Multi-dispute campaigns (Envoy negotiates with 5 providers in parallel, you approve one bundle)
- AgentCore deployment for always-on monitoring of renewal dates and price hikes

## License

MIT — see [LICENSE](LICENSE).
