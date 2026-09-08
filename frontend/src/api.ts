import type { Decision, Negotiation, Scenario, Settlement, Turn } from "./types";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then((r) => j<{ ok: boolean; model: string }>(r)),
  scenarios: () => fetch("/api/scenarios").then((r) => j<Scenario[]>(r)),
  negotiations: () => fetch("/api/negotiations").then((r) => j<Negotiation[]>(r)),
  createNegotiation: (text: string, scenarioId: string | null, title?: string) =>
    fetch("/api/negotiations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, scenario_id: scenarioId, title }),
    }).then((r) => j<{ id: string; title: string }>(r)),
  negotiation: (id: string) =>
    fetch(`/api/negotiations/${id}`).then(
      (r) =>
        j<{
          negotiation: Negotiation;
          turns: Turn[];
          decisions: Decision[];
          settlements: Settlement[];
        }>(r),
    ),
  pendingDecisions: () => fetch("/api/decisions").then((r) => j<Decision[]>(r)),
  respond: (id: string, action: "approved" | "declined", note?: string) =>
    fetch(`/api/decisions/${id}/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, note }),
    }).then((r) => j<{ ok: boolean }>(r)),
  ledger: () =>
    fetch("/api/ledger").then((r) =>
      j<{ saved: Record<string, number>; settlements: Settlement[] }>(r),
    ),
};
