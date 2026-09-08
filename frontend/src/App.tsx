import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { Decision, Negotiation, Scenario, Turn } from "./types";

const STATUS_META: Record<string, { label: string; color: string; pulse?: boolean }> = {
  queued: { label: "Queued", color: "bg-slate-700/60 text-slate-200" },
  working: { label: "Preparing your case", color: "bg-amber-500/15 text-amber-300", pulse: true },
  in_negotiation: { label: "Negotiating", color: "bg-sky-500/15 text-sky-300", pulse: true },
  needs_you: { label: "Needs you", color: "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40", pulse: true },
  settled: { label: "Settled", color: "bg-emerald-500/15 text-emerald-300" },
  declined: { label: "Escalated", color: "bg-violet-500/15 text-violet-300" },
  impasse: { label: "Impasse", color: "bg-orange-500/15 text-orange-300" },
  failed: { label: "Stalled", color: "bg-slate-700/60 text-slate-400" },
};

const INTENT_META: Record<string, { label: string; tone: string }> = {
  open: { label: "opening demand", tone: "text-sky-300 border-sky-400/30 bg-sky-400/10" },
  counter: { label: "counter", tone: "text-amber-300 border-amber-400/30 bg-amber-400/10" },
  firm: { label: "holding firm", tone: "text-orange-300 border-orange-400/30 bg-orange-400/10" },
  accept: { label: "agrees", tone: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10" },
  escalate: { label: "escalating", tone: "text-fuchsia-300 border-fuchsia-400/30 bg-fuchsia-400/10" },
  final: { label: "final offer", tone: "text-rose-300 border-rose-400/30 bg-rose-400/10" },
  consult_owner: { label: "asks you", tone: "text-rose-300 border-rose-400/30 bg-rose-400/10" },
  opened: { label: "", tone: "" },
  phase: { label: "", tone: "" },
  settled: { label: "", tone: "" },
  declined: { label: "", tone: "" },
  impasse: { label: "", tone: "" },
  needs_you: { label: "", tone: "" },
  owner_instruction: { label: "", tone: "" },
  error: { label: "", tone: "" },
};

function offerText(o: { kind: string; amount: number; currency: string; months: number; conditions: string } | null): string {
  if (!o) return "";
  const pct = o.amount && o.kind === "discount_months" ? `${o.amount}%` : o.amount ? `${o.currency} ${o.amount.toLocaleString()}` : "";
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
  return o.conditions ? `${label} · ${o.conditions}` : label;
}

function OfferChip({ offer }: { offer: NonNullable<Turn["offer"]> }) {
  return (
    <span className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-200">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
      {offerText(offer)}
    </span>
  );
}

function turnBubble(t: Turn) {
  if (t.side === "system") {
    const isBig = ["settled", "declined", "impasse", "needs_you"].includes(t.intent);
    return (
      <div key={t.id} className="flex justify-center py-1">
        <div
          className={`max-w-[80%] rounded-lg px-3 py-1.5 text-center text-xs ${
            isBig ? "bg-white/10 text-slate-100 font-medium" : "bg-white/[0.04] text-slate-400"
          }`}
        >
          {t.message}
        </div>
      </div>
    );
  }
  const isAdvocate = t.side === "advocate";
  const meta = INTENT_META[t.intent] ?? { label: t.intent, tone: "" };
  return (
    <div key={t.id} className={`flex ${isAdvocate ? "justify-end" : "justify-start"} py-1.5`}>
      <div className={`max-w-[82%] ${isAdvocate ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div className={`flex items-center gap-2 text-[11px] ${isAdvocate ? "flex-row-reverse" : ""}`}>
          <span className={`rounded-full px-2 py-0.5 font-semibold ${isAdvocate ? "bg-sky-500/20 text-sky-300" : "bg-rose-500/15 text-rose-300"}`}>
            {isAdvocate ? "Envoy · your agent" : "Company agent"}
          </span>
          {meta.label && <span className={`rounded-full border px-2 py-0.5 ${meta.tone}`}>{meta.label}</span>}
        </div>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isAdvocate
              ? "rounded-br-md bg-sky-950/60 text-sky-50 ring-1 ring-sky-500/20"
              : "rounded-bl-md bg-[#171c25] text-slate-100 ring-1 ring-white/10"
          }`}
        >
          {t.message}
        </div>
        {t.offer && <OfferChip offer={t.offer} />}
      </div>
    </div>
  );
}

function DecisionCard({ d, onRespond }: { d: Decision; onRespond: (id: string, a: "approved" | "declined", note?: string) => void }) {
  const [note, setNote] = useState("");
  const kindLabel = d.kind === "settlement_approval" ? "Settlement approval" : d.kind === "impasse_review" ? "Impasse: their best offer" : "Envoy needs your call";
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-gradient-to-b from-rose-500/10 to-transparent p-4 shadow-lg shadow-rose-950/30">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-500/20 text-sm">🔔</span>
        <span className="text-xs font-semibold uppercase tracking-wider text-rose-300">{kindLabel}</span>
      </div>
      <p className="text-sm leading-relaxed text-slate-100">{d.question}</p>
      {d.payload?.offer && <div className="mt-2"><OfferChip offer={d.payload.offer} /></div>}
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note to your agent…"
        className="mt-3 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-500 focus:border-rose-400/40"
      />
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onRespond(d.id, "approved", note || undefined)}
          className="flex-1 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400"
        >
          Approve
        </button>
        <button
          onClick={() => onRespond(d.id, "declined", note || undefined)}
          className="flex-1 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:bg-white/10"
        >
          Decline
        </button>
      </div>
    </div>
  );
}

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

  const current = useMemo(() => negotiations.find((n) => n.id === selected) ?? null, [negotiations, selected]);

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

  const savedStr = Object.entries(saved)
    .map(([cur, v]) => `${cur} ${v.toLocaleString()}`)
    .join("  ·  ");

  return (
    <div className="flex h-full">
      {/* ---------------- sidebar ---------------- */}
      <aside className="flex w-[300px] shrink-0 flex-col border-r border-white/5 bg-[#0c1017]">
        <div className="border-b border-white/5 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-indigo-600 text-sm font-black text-white">E</span>
            <div>
              <div className="text-sm font-bold tracking-tight">Envoy</div>
              <div className="text-[11px] text-slate-500">Your negotiating agent</div>
            </div>
          </div>
          <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-emerald-400/80">Saved by your Envoy</div>
            <div className="text-sm font-bold text-emerald-300">{savedStr || "— nothing yet, feed it a dispute"}</div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3">
          {negotiations.map((n) => {
            const s = STATUS_META[n.status] ?? { label: n.status, color: "bg-slate-700/60" };
            const active = n.id === selected;
            return (
              <button
                key={n.id}
                onClick={() => setSelected(n.id)}
                className={`mb-1.5 w-full rounded-xl px-3 py-2.5 text-left transition ${
                  active ? "bg-white/10 ring-1 ring-white/15" : "hover:bg-white/5"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="line-clamp-2 text-[13px] font-medium leading-snug text-slate-200">{n.title}</span>
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${s.color}`}>
                    {s.pulse && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current align-middle" />}
                    {s.label}
                  </span>
                  {n.outcome && <span className="text-[10px] text-emerald-300/90">{n.outcome}</span>}
                </div>
              </button>
            );
          })}
        </div>

        <div className="border-t border-white/5 p-3">
          <div className="mb-2 flex flex-wrap gap-1">
            <button
              onClick={() => setScenarioId("")}
              className={`rounded-full px-2.5 py-1 text-[11px] transition ${
                scenarioId === "" ? "bg-sky-500/25 text-sky-200 ring-1 ring-sky-400/40" : "bg-white/5 text-slate-400 hover:bg-white/10"
              }`}
            >
              Free text
            </button>
            {scenarios.map((s) => (
              <button
                key={s.id}
                onClick={() => setScenarioId(s.id)}
                className={`rounded-full px-2.5 py-1 text-[11px] transition ${
                  scenarioId === s.id ? "bg-sky-500/25 text-sky-200 ring-1 ring-sky-400/40" : "bg-white/5 text-slate-400 hover:bg-white/10"
                }`}
              >
                {s.provider}
              </button>
            ))}
          </div>
          <textarea
            value={composer}
            onChange={(e) => setComposer(e.target.value)}
            rows={3}
            placeholder="e.g. My internet bill jumped 38% mid-contract…"
            className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-[13px] outline-none placeholder:text-slate-500 focus:border-sky-400/40"
          />
          <button
            onClick={submit}
            disabled={busy || !composer.trim()}
            className="mt-2 w-full rounded-xl bg-sky-500 py-2 text-sm font-semibold text-sky-950 transition hover:bg-sky-400 disabled:opacity-40"
          >
            {busy ? "Dispatching…" : "Send to Envoy"}
          </button>
          <div className="mt-2 truncate text-center text-[10px] text-slate-600">advocate: {model || "…"}</div>
        </div>
      </aside>

      {/* ---------------- negotiation room ---------------- */}
      <main className="flex min-w-0 flex-1 flex-col">
        {current ? (
          <>
            <header className="flex items-center justify-between border-b border-white/5 px-6 py-3.5">
              <div className="min-w-0">
                <h1 className="truncate text-sm font-semibold">{current.title}</h1>
                <p className="text-[11px] text-slate-500">
                  {["working", "in_negotiation"].includes(current.status)
                    ? "Your agent is handling it. You are not needed."
                    : current.status === "needs_you"
                      ? "Your agent hit a point that needs a human."
                      : STATUS_META[current.status]?.label}
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${STATUS_META[current.status]?.color ?? ""}`}>
                {STATUS_META[current.status]?.label ?? current.status}
              </span>
            </header>
            <div ref={feedRef} className="flex-1 overflow-y-auto px-6 py-4">
              {turns.map(turnBubble)}
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <div className="text-4xl">🤝</div>
            <h2 className="text-lg font-semibold">Companies deployed agents to talk to you.</h2>
            <p className="max-w-md text-sm text-slate-400">
              Envoy deploys yours. Hand it a billing dispute, a refund claim, a price hike —
              it builds the case and negotiates with the company's agent. You only show up when
              there's a real decision to make.
            </p>
          </div>
        )}
      </main>

      {/* ---------------- decisions ---------------- */}
      <aside className="flex w-[340px] shrink-0 flex-col border-l border-white/5 bg-[#0c1017]">
        <div className="border-b border-white/5 px-4 py-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Decisions</h2>
          <p className="text-[11px] text-slate-600">Only what genuinely needs a human</p>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {pending.length === 0 && (
            <div className="rounded-xl border border-dashed border-white/10 p-4 text-center text-xs text-slate-500">
              All quiet. Envoy is either working or everything is settled.
            </div>
          )}
          {pending.map((d) => (
            <DecisionCard key={d.id} d={d} onRespond={respond} />
          ))}
        </div>
      </aside>
    </div>
  );
}
