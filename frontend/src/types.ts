export interface Offer {
  kind: string;
  amount: number;
  currency: string;
  months: number;
  conditions: string;
}

export interface Turn {
  id: string;
  neg_id: string;
  ts: number;
  side: "advocate" | "provider" | "system";
  intent: string;
  message: string;
  offer: Offer | null;
}

export interface Decision {
  id: string;
  neg_id: string;
  ts: number;
  kind: string;
  question: string;
  payload: { offer?: Offer; summary?: string; accepted_by?: string };
  status: string;
  response: string | null;
}

export interface Settlement {
  id: string;
  neg_id: string;
  ts: number;
  amount: number;
  currency: string;
  terms: string;
  reference: string;
}

export interface Negotiation {
  id: string;
  title: string;
  raw_text: string;
  scenario_id: string | null;
  status: string;
  strategy: string | null;
  outcome: string | null;
  summary: string | null;
  created_at: number;
}

export interface Scenario {
  id: string;
  label: string;
  provider: string;
}
