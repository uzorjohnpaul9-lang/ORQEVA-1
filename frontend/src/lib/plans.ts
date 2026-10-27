// Single source of truth for subscription tiers and their feature matrix.

export type Tier = "free" | "premium" | "vip";

export const TIER_ORDER: Tier[] = ["free", "premium", "vip"];

const RANK: Record<string, number> = { free: 0, premium: 1, vip: 2 };

export function tierRank(tier?: string | null): number {
  return RANK[(tier || "free").toLowerCase()] ?? 0;
}

export function tierLabel(tier?: string | null): string {
  const t = (tier || "free").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function tierBadgeVariant(tier?: string | null): "gray" | "yellow" | "purple" {
  const t = (tier || "free").toLowerCase();
  return t === "vip" ? "purple" : t === "premium" ? "yellow" : "gray";
}

export const PLAN_PRICES: Record<Tier, number> = { free: 0, premium: 49, vip: 199 };

// Yearly prices mirror the backend payment config (2 months free); the billing
// page reads the authoritative numbers from /api/billing/plans.
export const PLAN_ANNUAL_PRICES: Record<Tier, number> = { free: 0, premium: 490, vip: 1990 };

export interface TierInfo {
  tier: Tier;
  name: string;
  tagline: string;
  perks: string[];
}

export const TIERS: TierInfo[] = [
  {
    tier: "free",
    name: "Free",
    tagline: "Get started with forex signals.",
    perks: ["Forex signals", "Paper auto-trade", "30 requests/min"],
  },
  {
    tier: "premium",
    name: "Premium",
    tagline: "Stocks & commodities, faster alerts.",
    perks: ["Everything in Free", "Stock + commodity signals", "Stock auto-trade", "120 requests/min"],
  },
  {
    tier: "vip",
    name: "VIP",
    tagline: "Full access incl. crypto & memecoins.",
    perks: [
      "Everything in Premium",
      "Crypto + memecoin signals",
      "Crypto auto-trade",
      "Priority support",
      "300 requests/min",
    ],
  },
];

export type FeatureValue = boolean | string;

export interface FeatureRow {
  label: string;
  free: FeatureValue;
  premium: FeatureValue;
  vip: FeatureValue;
}

export const FEATURE_MATRIX: FeatureRow[] = [
  { label: "Forex signals", free: true, premium: true, vip: true },
  { label: "Stock signals", free: false, premium: true, vip: true },
  { label: "Commodity signals", free: false, premium: true, vip: true },
  { label: "Crypto & memecoin signals", free: false, premium: false, vip: true },
  { label: "Auto-trade markets", free: "Forex only", premium: "Forex + Stocks + Commodities", vip: "All markets" },
  { label: "Signal latency", free: "5 min", premium: "1 min", vip: "Real-time" },
  { label: "Telegram alerts", free: false, premium: true, vip: true },
  { label: "API rate limit", free: "30/min (for reference)", premium: "120/min (for reference)", vip: "300/min (for reference)" },
  { label: "Custom risk profiles", free: false, premium: true, vip: true },
  { label: "Priority support", free: false, premium: false, vip: true },
];
