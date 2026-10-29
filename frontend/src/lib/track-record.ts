import { API_BASE } from "@/lib/api";

export type TrackRecordOutcome = "tp" | "sl" | "expired" | "breakeven";

export interface TrackRecordPublicRow {
  signal_id: string;
  opened_at: string;
  closed_at: string | null;
  symbol: string;
  market: string;
  direction: "buy" | "sell";
  entry: number | null;
  stop: number | null;
  target: number | null;
  exit: number | null;
  outcome: TrackRecordOutcome;
  r_multiple: number | null;
  r_multiple_net: number | null;
  data_source: "live" | "simulated" | null;
  resolution_basis: string;
  resolution_version: string;
  strategy: string | null;
}

export interface TrackRecordMarket {
  market: string;
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number;
}

export interface TrackRecordStrategy {
  strategy: string;
  markets: string[];
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number;
}

export interface TrackRecordSnapshot {
  status: "collecting" | "live";
  sample: { resolved: number; needed: number; remaining: number; progress_pct: number };
  resolved: number;
  wins: number;
  losses: number;
  tp: number;
  sl: number;
  expired: number;
  breakeven: number;
  win_rate: number;
  win_rate_tp_sl: number | null;
  avg_r_gross: number;
  avg_r_net: number;
  cost_r: number;
  by_market: TrackRecordMarket[];
  by_strategy: TrackRecordStrategy[];
  excluded: { simulated: number; unknown: number; legacy: number };
  cohort_started_at?: string | null;
  legacy_cohort?: {
    resolved: number;
    win_rate_tp_sl: number | null;
    avg_r_gross: number;
    note: string;
  } | null;
  first_live_at: string | null;
  last_resolved_at: string | null;
  live_only: boolean;
  generated_at: string;
  resolution_version: string;
  schema: string;
  methodology: Record<string, unknown>;
  recent: TrackRecordPublicRow[];
}

export const EMPTY_SNAPSHOT: TrackRecordSnapshot = {
  status: "collecting",
  sample: { resolved: 0, needed: 30, remaining: 30, progress_pct: 0 },
  resolved: 0,
  wins: 0,
  losses: 0,
  tp: 0,
  sl: 0,
  expired: 0,
  breakeven: 0,
  win_rate: 0,
  win_rate_tp_sl: null,
  avg_r_gross: 0,
  avg_r_net: 0,
  cost_r: 0.05,
  by_market: [],
  by_strategy: [],
  excluded: { simulated: 0, unknown: 0, legacy: 0 },
  first_live_at: null,
  last_resolved_at: null,
  live_only: true,
  generated_at: "",
  resolution_version: "",
  schema: "unknown",
  methodology: {},
  recent: [],
};

export const TRACK_RECORD_CSV_URL = `${API_BASE}/api/track-record.csv`;

export async function fetchTrackRecord(signal?: AbortSignal): Promise<TrackRecordSnapshot> {
  const res = await fetch(`${API_BASE}/api/track-record`, {
    signal,
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`track record unavailable (${res.status})`);
  return (await res.json()) as TrackRecordSnapshot;
}

export function formatR(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}R`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}
