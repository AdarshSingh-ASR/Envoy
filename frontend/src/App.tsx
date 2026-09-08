import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { Decision, Negotiation, Scenario, Turn } from "./types";

/* ------------------------------------------------------------ descriptors */

const STATUS_META: Record<string, { label: string; live?: boolean }> = {
  queued: { label: "Queued" },
  working: { label: "Preparing the case", live: true },
  in_negotiation: { label: "Negotiating", live: true },
  needs_you: { label: "Decision required", live: true },
  settled: { label: "Settled" },
  declined: { label: "Escalated" },
  impasse: { label: "Impasse" },
  failed: { label: "Stalled" },
};

const INTENT_META: Record<string, string> = {
  open: "Opening demand",
  counter: "Counter",
  firm: "Holding firm",
  accept: "Agrees",
  escalate: "Escalating",
  final: "Final offer",
  consult_owner: "Asks you",
};

const META_TODAY = new Date().toLocaleDateString("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

function offerText(o: {
  kind: string;
  amount: number;
  currency: string;
  months: number;
  conditions: string;
} | null): string {
  if (!o) return "";
  const pct =
    o.amount && o.kind === "discount_months"
      ? `${o.amount}%`
      : o.amount
        ? `${o.currency} ${o.amount.toLocaleString()}`
        : "";
  const base: Record<string, string> = {
    full_refund: "Full refund",
    partial_refund: `Partial refund ${pct}`,
    credit: `Credit ${pct}`,
    voucher: `Voucher ${pct}`,
    fee_waiver: o.amount ? `Fee of ${pct} waived` : "Fee waived",
    discount_months: `${pct || "Discount"} off for ${o.months} months`,
    price_lock: `Price locked ${o.months} months`,
    none: "No offer",
  };
  const label = base[o.kind] ?? o.kind;
  return o.conditions ? `${label} — ${o.conditions}` : label;
}

/* ------------------------------------------------------------------- bits */

function OfferChip({ offer }: { offer: NonNullable<Turn["offer"]> }) {
  return (
    <span className="font-mono2 mt-2 inline-block border px-2.5 py-1 text-[10px] font-medium"
      style={{ borderColor: "var(--faint)", color: "var(--ink)", background: "var(--soft)" }}>
      ⟡ {offerText(offer)}
    </span>
  );
}

function TurnRow({ t }: { t: Turn }) {
  if (t.side === "system") {
    const big = ["settled", "declined", "impasse", "needs_you"].includes(t.intent);
    const short = t.message.length <= 70;
    if (short) {
      return (
        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1" style={{ background: "var(--ink)", opacity: 0.35 }} />
          <div
            className="font-mono2 px-2 text-center text-[10px]"
            style={{ color: t.intent === "settled" ? "var(--ok)" : t.intent === "needs_you" ? "var(--accent)" : "var(--muted)" }}
          >
            {big ? `— ${t.message} —` : t.message}
          </div>
          <div className="h-px flex-1" style={{ background: "var(--ink)", opacity: 0.35 }} />
        </div>
      );
    }
    // long dispatch note: serif body with a mono kicker
    const accent = t.intent === "needs_you" || t.intent === "impasse";
    return (
      <div className="my-5 border px-4 py-3" style={{ borderColor: accent ? "var(--accent)" : "var(--faint)", background: "var(--panel)", borderWidth: accent ? "1.5px" : "1px" }}>
        <div
          className="font-mono2 mb-1.5 text-[9.5px] font-semibold"
          style={{ color: accent ? "var(--accent)" : "var(--muted)" }}
        >
          Desk note · {t.intent}
        </div>
        <p className="font-body text-[14px] leading-relaxed">{t.message}</p>
        {t.offer && <div><OfferChip offer={t.offer} /></div>}
      </div>
    );
  }

  const isEnvoy = t.side === "advocate";
  const intent = INTENT_META[t.intent] ?? t.intent;
  return (
    <div className={`py-3 ${isEnvoy ? "text-right" : ""}`}>
      <div
        className={`font-mono2 mb-1 flex items-center gap-2 text-[10px] ${isEnvoy ? "justify-end" : ""}`}
        style={{ color: isEnvoy ? "var(--accent)" : "var(--muted)" }}
      >
        {isEnvoy ? (
          <>
            <span>{intent && `· ${intent}`}</span>
            <span className="font-semibold" style={{ color: "var(--ink)" }}>Envoy — your agent</span>
          </>
        ) : (
          <>
            <span className="font-semibold" style={{ color: "var(--ink)" }}>Company agent</span>
            {intent && <span>· {intent}</span>}
          </>
        )}
      </div>
      <p
        className="font-body inline-block max-w-[85%] text-[15px] leading-relaxed"
        style={{
          borderTop: "1px solid var(--ink)",
          borderBottom: "1px solid var(--ink)",
          padding: "8px 2px",
        }}
      >
        {t.message}
      </p>
      <div className={isEnvoy ? "" : ""}>{t.offer && <OfferChip offer={t.offer} />}</div>
    </div>
  );
}

function DecisionCard({ d, onRespond }: { d: Decision; onRespond: (id: string, a: "approved" | "declined", note?: string) => void }) {
  const [note, setNote] = useState("");
  const kindLabel =
    d.kind === "settlement_approval"
      ? "Settlement approval"
      : d.kind === "impasse_review"
        ? "Impasse — their best offer"
        : "Envoy needs your call";
  return (
    <div className="mb-5 border-2 p-4" style={{ borderColor: "var(--accent)", background: "var(--panel)" }}>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono2 text-[10px] font-semibold" style={{ color: "var(--accent)" }}>
          {kindLabel}
        </span>
        <span className="font-mono2 text-[9px]" style={{ color: "var(--muted)" }}>{META_TODAY}</span>
      </div>
      <p className="font-body text-[15px] leading-relaxed">{d.question}</p>
      {d.payload?.offer && <div className="mt-2"><OfferChip offer={d.payload.offer} /></div>}
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Note to your agent (optional)…"
        className="font-body mt-3 w-full bg-transparent pb-1 text-sm outline-none"
        style={{ borderBottom: "1px solid var(--faint)", color: "var(--ink)" }}
      />
      <div className="mt-4 flex gap-2">
        <button
          onClick={() => onRespond(d.id, "approved", note || undefined)}
          className="font-mono2 flex-1 border px-3 py-2 text-[11px] font-semibold transition"
          style={{ background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" }}
        >
          Approve →
        </button>
        <button
          onClick={() => onRespond(d.id, "declined", note || undefined)}
          className="font-mono2 flex-1 border bg-transparent px-3 py-2 text-[11px] font-semibold transition hover:opacity-70"
          style={{ borderColor: "var(--ink)", color: "var(--ink)" }}
        >
          Decline ✕
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------- app */

export default function App() {
  const [negotiations, setNegotiations] = useState<Negotiation[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState<Decision[]>([]);
  const [saved, setSaved] = useState<Record<string, number>>({});
  const [model, setModel] = useState("");
  const [composer, setComposer] = useState("");
  const [scenarioId, setScenarioId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [night, setNight] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  const refreshLists = useCallback(async () => {
    const [ns, ds, led] = await Promise.all([api.negotiations(), api.pendingDecisions(), api.ledger()]);
    setNegotiations(ns);
    setPending(ds);
    setSaved(led.saved);
  }, []);

  useEffect(() => {
    api.health().then((h) => setModel(h.model)).catch(() => {});
    api.scenarios().then(setScenarios).catch(() => {});
  }, []);

  useEffect(() => {
    refreshLists().catch(() => {});
    const iv = setInterval(() => refreshLists().catch(() => {}), 2500);
    return () => clearInterval(iv);
  }, [refreshLists]);

  useEffect(() => {
    if (!selected) return;
    let stop = false;
    const poll = async () => {
      try {
        const d = await api.negotiation(selected);
        if (!stop) setTurns(d.turns);
      } catch {
        /* ignore */
      }
    };
    poll();
    const iv = setInterval(poll, 2000);
    return () => {
      stop = true;
      clearInterval(iv);
    };
  }, [selected]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
  }, [turns.length]);

  const current = useMemo(
    () => negotiations.find((n) => n.id === selected) ?? null,
    [negotiations, selected],
  );

  const submit = async () => {
    if (!composer.trim()) return;
    setBusy(true);
    try {
      const r = await api.createNegotiation(composer.trim(), scenarioId || null);
      setComposer("");
      setSelected(r.id);
      await refreshLists();
    } finally {
      setBusy(false);
    }
  };

  const respond = async (id: string, a: "approved" | "declined", note?: string) => {
    await api.respond(id, a, note);
    await refreshLists();
  };

  const clearLedger = async () => {
    await api.reset();
    setSelected(null);
    setTurns([]);
    await refreshLists();
  };

  const savedStr =
    Object.entries(saved)
      .map(([cur, v]) => `${cur} ${v.toLocaleString()}`)
      .join("  ·  ") || "0";
  const status = current ? (STATUS_META[current.status] ?? { label: current.status }) : null;

  const paper = "var(--paper)";
  const panel = "var(--panel)";
  const ink = "var(--ink)";
  const muted = "var(--muted)";
  const faint = "var(--faint)";

  return (
    <div data-theme={night ? "ink" : "paper"} className="flex h-full min-w-[960px] flex-col" style={{ background: paper, color: ink }}>
      {/* ------- top meta strip ------- */}
      <div
        className="font-mono2 flex items-center justify-between border-b px-5 py-1.5 text-[9.5px]"
        style={{ borderColor: ink, color: muted }}
      >
        <span>Field edition — {META_TODAY} · Dispute desk</span>
        <span className="flex items-center gap-1.5">
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${status?.live ? "animate-pulse" : ""}`}
            style={{ background: "var(--accent)" }}
          />
          Negotiation live
        </span>
        <button
          onClick={() => setNight(!night)}
          className="font-semibold transition hover:opacity-70"
          style={{ color: ink }}
          title="Toggle ink night"
        >
          {night ? "● Day paper" : "● Ink night"}
        </button>
      </div>

      {/* ------- masthead ------- */}
      <header className="flex items-end justify-between border-b px-5 pb-3 pt-4" style={{ borderColor: ink }}>
        <div>
          <h1 className="font-display text-[44px] font-extrabold leading-none tracking-tight">Envoy</h1>
          <p className="font-display mt-1 text-[15px] italic" style={{ color: "var(--accent)" }}>
            The negotiating agent.
          </p>
        </div>
        <div className="text-right">
          <div className="font-mono2 text-[9.5px]" style={{ color: muted }}>Saved by your envoy</div>
          <div className="font-display text-[26px] font-bold leading-tight" style={{ color: "var(--ok)" }}>
            {savedStr}
          </div>
        </div>
      </header>

      {/* ------- three columns ------- */}
      <div className="grid min-h-0 flex-1 grid-cols-[240px_1fr_300px]">
        {/* dispute ledger */}
        <aside className="flex min-h-0 flex-col border-r" style={{ borderColor: ink, background: panel }}>
          <div
            className="font-mono2 sticky top-0 z-10 flex shrink-0 items-center justify-between border-b px-4 py-2 text-[9.5px] font-semibold"
            style={{ borderColor: ink, background: panel, color: muted }}
          >
            <span>01 — Dispute ledger</span>
            <button
              onClick={clearLedger}
              className="font-semibold transition hover:opacity-60"
              style={{ color: "var(--accent)" }}
              title="Wipe all negotiations and the savings ledger"
            >
              Clear ✕
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {negotiations.map((n, i) => {
              const s = STATUS_META[n.status] ?? { label: n.status };
              const active = n.id === selected;
              return (
                <button
                  key={n.id}
                  onClick={() => setSelected(n.id)}
                  className="mb-0 block w-full border-b px-2 py-3 text-left transition"
                  style={{
                    borderColor: faint,
                    background: active ? "var(--soft)" : "transparent",
                  }}
                >
                  <div className="font-mono2 mb-1 text-[9px]" style={{ color: faint }}>
                    No. {String(negotiations.length - i).padStart(2, "0")}
                  </div>
                  <div className="font-body text-[13.5px] font-semibold leading-snug">{n.title}</div>
                  <div className="font-mono2 mt-1.5 flex items-center gap-2 text-[9px]" style={{ color: s.live ? "var(--accent)" : muted }}>
                    {s.live && <span className="inline-block h-1 w-1 animate-pulse rounded-full" style={{ background: "var(--accent)" }} />}
                    {s.label}
                    {n.outcome && <span style={{ color: "var(--ok)" }}>— {n.outcome}</span>}
                  </div>
                </button>
              );
            })}
          </div>

          {/* composer */}
          <div className="shrink-0 border-t p-4" style={{ borderColor: ink }}>
            <div className="font-mono2 mb-2 text-[9.5px] font-semibold" style={{ color: muted }}>02 — File a dispute</div>
            <div className="mb-2 flex flex-wrap gap-1">
              <button
                onClick={() => setScenarioId("")}
                className="font-mono2 border px-2 py-1 text-[9px] transition"
                style={{
                  borderColor: scenarioId === "" ? ink : faint,
                  background: scenarioId === "" ? ink : "transparent",
                  color: scenarioId === "" ? paper : muted,
                }}
              >
                Free text
              </button>
              {scenarios.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setScenarioId(s.id)}
                  className="font-mono2 border px-2 py-1 text-[9px] transition"
                  style={{
                    borderColor: scenarioId === s.id ? ink : faint,
                    background: scenarioId === s.id ? ink : "transparent",
                    color: scenarioId === s.id ? paper : muted,
                  }}
                >
                  {s.provider}
                </button>
              ))}
            </div>
            <textarea
              value={composer}
              onChange={(e) => setComposer(e.target.value)}
              rows={3}
              placeholder="My internet bill jumped 38% mid-contract…"
              className="font-body w-full resize-none bg-transparent text-[13px] leading-relaxed outline-none"
              style={{ borderBottom: `1px solid ${faint}`, color: ink }}
            />
            <button
              onClick={submit}
              disabled={busy || !composer.trim()}
              className="font-mono2 mt-3 w-full border py-2 text-[11px] font-semibold transition disabled:opacity-40"
              style={{ background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" }}
            >
              {busy ? "Dispatching…" : "Send to Envoy →"}
            </button>
            <div className="font-mono2 mt-2 truncate text-center text-[8.5px]" style={{ color: faint }}>
              Advocate: {model || "—"}
            </div>
          </div>
        </aside>

        {/* negotiation room */}
        <main className="flex min-h-0 flex-col" style={{ background: paper }}>
          {current ? (
            <>
              <div
                className="font-mono2 flex items-center justify-between border-b px-6 py-2 text-[9.5px]"
                style={{ borderColor: ink, color: muted }}
              >
                <span>03 — The negotiation room</span>
                <span style={{ color: status?.live ? "var(--accent)" : muted }}>
                  {status?.live ? "You are not needed. Watch quietly." : status?.label}
                </span>
              </div>
              <div ref={feedRef} className="min-h-0 flex-1 overflow-y-auto px-8 py-4">
                <div className="mx-auto max-w-[640px]">
                  {turns.map((t) => (
                    <TurnRow key={t.id} t={t} />
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center px-10 text-center">
              <div className="font-mono2 mb-4 text-[9.5px]" style={{ color: muted }}>03 — The negotiation room</div>
              <h2 className="font-display text-[34px] font-bold leading-tight">
                Companies deployed agents
                <br />
                <span className="italic" style={{ color: "var(--accent)" }}>to talk to you.</span>
              </h2>
              <p className="font-body mt-4 max-w-md text-[15px] leading-relaxed" style={{ color: muted }}>
                Envoy deploys yours. Hand it a billing dispute, a refund claim, a price hike —
                it builds the case and negotiates with the company's agent. You appear only when
                there is a real decision to make.
              </p>
            </div>
          )}
        </main>

        {/* decisions */}
        <aside className="min-h-0 overflow-y-auto border-l" style={{ borderColor: ink, background: panel }}>
          <div className="font-mono2 sticky top-0 z-10 border-b px-4 py-2 text-[9.5px] font-semibold" style={{ borderColor: ink, background: panel, color: muted }}>
            04 — Decisions
          </div>
          <div className="p-4">
            {pending.length === 0 ? (
              <div className="font-body border p-4 text-center text-[13px] italic" style={{ borderColor: faint, color: muted }}>
                All quiet. Envoy is either working, or everything is settled.
              </div>
            ) : (
              pending.map((d) => <DecisionCard key={d.id} d={d} onRespond={respond} />)
            )}
          </div>
        </aside>
      </div>

      {/* ------- footer strip ------- */}
      <div
        className="font-mono2 flex items-center justify-between border-t px-5 py-1.5 text-[9px]"
        style={{ borderColor: ink, color: faint }}
      >
        <span>Observe · Decide · Act · Verify — the completion loop</span>
        <span>Built with Strands Agents SDK</span>
      </div>
    </div>
  );
}
