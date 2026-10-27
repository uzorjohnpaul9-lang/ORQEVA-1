"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FEATURE_MATRIX, tierBadgeVariant, tierLabel, type FeatureValue } from "@/lib/plans";
import type { Invoice, Subscription } from "@/lib/types";

interface Plan {
  tier: string;
  name: string;
  price_usd: number;
  duration_days: number;
  annual_price_usd?: number;
  annual_days?: number;
  annual_savings_usd?: number;
}
interface BankCard {
  bank_name: string;
  account_name: string;
  account_number: string;
  branch: string;
  instructions: string;
}
interface Gateway { provider: string; display_name: string }
interface Corridor { id: string; label: string; currency: string; kind: string }

type Rail = "bachs" | "crypto" | "manual";
type PayState = "none" | "returning" | "confirmed" | "pending";

const STATUS_VARIANT: Record<string, "green" | "red" | "yellow" | "gray" | "blue"> = {
  approved: "green",
  pending: "yellow",
  rejected: "red",
  refunded: "blue",
  cancelled: "gray",
  expired: "gray",
};

const RAIL_LABEL: Record<string, string> = {
  bachs: "Card, bank & mobile money",
  crypto: "USDT (TRC-20)",
  manual: "Manual bank transfer",
};

/** Backend error codes -> something a user can act on. */
const ERROR_COPY: Record<string, string> = {
  checkout_unavailable:
    "The payment provider could not start a checkout. Try again in a moment, or use one of the other ways to pay.",
  invalid_method: "That payment method is not available.",
  invalid_payment_method: "That payment method is not available for this plan.",
  invalid_tier: "That plan is not available.",
  invalid_term: "That billing period is not available.",
  "invoice expired": "That invoice has expired. Create a new one to pay.",
};

function describeError(err: unknown): string {
  const raw = err instanceof Error ? err.message.trim() : "";
  if (!raw) return "Something went wrong. Please try again.";
  if (ERROR_COPY[raw]) return ERROR_COPY[raw];
  if (raw === "internal") {
    return "The server hit an unexpected error. Your card was not charged - please try again.";
  }
  if (/Failed to fetch|NetworkError|timeout|abort/i.test(raw)) {
    return "Could not reach the server. Check your connection and try again.";
  }
  return raw;
}

function RailIcon({ kind, className }: { kind: string; className?: string }) {
  const common = { className: clsx("w-5 h-5", className), fill: "none", stroke: "currentColor", strokeWidth: 1.8, viewBox: "0 0 24 24" };
  if (kind === "card") {
    return (
      <svg {...common}>
        <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
        <path d="M2.5 9.5h19M6 15h4" strokeLinecap="round" />
      </svg>
    );
  }
  if (kind === "bank") {
    return (
      <svg {...common}>
        <path d="M3 9.5 12 4l9 5.5M4.5 9.5V19M9.5 9.5V19M14.5 9.5V19M19.5 9.5V19M3 19.5h18" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (kind === "momo") {
    return (
      <svg {...common}>
        <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
        <path d="M10 6.5h4M11 18h2" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.5 8.5h4a2 2 0 0 1 0 4h-4v4h4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function FeatureCell({ value }: { value: FeatureValue }) {
  if (value === true) return <span className="text-green font-medium">Yes</span>;
  if (value === false) return <span className="text-text-muted">-</span>;
  return <span className="text-text-secondary">{value}</span>;
}

function corridorLabel(inv: Invoice): string {
  if (inv.payment_method) {
    const known: Record<string, string> = {
      USD_CARD: "Card (USD)",
      NGN_CARD: "Card (NGN)",
      NGN_BANK_TRANSFER: "Bank transfer (NGN)",
      CRYPTO: "Crypto",
    };
    if (known[inv.payment_method]) return known[inv.payment_method];
    if (inv.payment_method.startsWith("MOMO_")) {
      return `Mobile money (${inv.payment_method.replace("MOMO_", "")})`;
    }
  }
  if (inv.provider === "crypto") {
    return `USDT ${(inv.network || "").replace("usdt_", "").toUpperCase()}`.trim();
  }
  if (inv.provider === "bachs") return "Bachs checkout";
  if (inv.provider === "manual") return "Manual bank transfer";
  return inv.method;
}

export default function BillingPage() {
  const { token, user } = useAuth();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [gateways, setGateways] = useState<Gateway[]>([]);
  const [corridors, setCorridors] = useState<Corridor[]>([]);
  const [bankCard, setBankCard] = useState<BankCard | null>(null);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [payState, setPayState] = useState<PayState>("none");

  // payment form
  const [tier, setTier] = useState("premium");
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [rail, setRail] = useState<Rail>("bachs");
  const [corridor, setCorridor] = useState<string>("");
  const [promoCode, setPromoCode] = useState("");
  const [paying, setPaying] = useState(false);

  // payment-proof modal
  const [proofFor, setProofFor] = useState<Invoice | null>(null);
  const [proofValue, setProofValue] = useState("");
  const [proofBusy, setProofBusy] = useState(false);

  const bachsReady = gateways.some((g) => g.provider === "bachs");
  const selectedPlan = plans.find((p) => p.tier === tier) || null;
  const price =
    cycle === "annual" && selectedPlan?.annual_price_usd
      ? selectedPlan.annual_price_usd
      : selectedPlan?.price_usd ?? 0;

  const refresh = useCallback(
    async (opts?: { noCache?: boolean }) => {
      if (!token) return;
      const [plansRes, subRes, invRes] = await Promise.allSettled([
        api<{ plans: Plan[]; bank_card?: BankCard; gateways?: Gateway[]; payment_methods?: Corridor[] }>(
          "/api/billing/plans",
          { token, noCache: opts?.noCache },
        ),
        api<Subscription>("/api/billing/subscription", { token, noCache: opts?.noCache }),
        api<Invoice[]>("/api/billing/invoices", { token, noCache: opts?.noCache }),
      ]);

      const failed: string[] = [];

      if (plansRes.status === "fulfilled") {
        const data = plansRes.value;
        setPlans(data?.plans ?? []);
        setBankCard(data?.bank_card ?? null);
        setGateways(Array.isArray(data?.gateways) ? data!.gateways! : []);
        setCorridors(Array.isArray(data?.payment_methods) ? data!.payment_methods! : []);
      } else {
        failed.push("plans");
      }

      if (subRes.status === "fulfilled") {
        setSub(subRes.value ?? null);
      } else {
        failed.push("subscription");
      }

      if (invRes.status === "fulfilled") {
        setInvoices(Array.isArray(invRes.value) ? invRes.value : []);
      } else {
        failed.push("invoices");
      }

      setLoadError(
        failed.length
          ? `Could not load ${failed.join(", ")}. The rest of your billing data is still shown below.`
          : null,
      );
    },
    [token],
  );

  useEffect(() => {
    if (!token) return;
    refresh();
  }, [token, refresh]);

  // Coming back from the Bachs checkout: strip the query param and wait for
  // the webhook to land so the invoice flips to approved.
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!token) return;
    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    if (status !== "paid" && status !== "cancelled") return;

    params.delete("status");
    const rest = params.toString();
    window.history.replaceState(null, "", rest ? `?${rest}` : window.location.pathname);

    if (status === "cancelled") {
      setNotice("Checkout cancelled. Nothing was charged - pick a plan and try again whenever you are ready.");
      return;
    }

    setPayState("returning");
    setNotice("Payment submitted. Waiting for the provider to confirm it...");

    let tries = 0;
    const poll = async () => {
      tries += 1;
      try {
        const invs = await api<Invoice[]>("/api/billing/invoices", { token, noCache: true });
        setInvoices(Array.isArray(invs) ? invs : []);
        if (Array.isArray(invs) && invs.some((i) => i.status === "approved")) {
          setPayState("confirmed");
          setNotice("Payment confirmed. Your plan is active now.");
          await refresh({ noCache: true });
          return;
        }
      } catch {
        /* keep polling; the webhook is the source of truth */
      }
      if (tries < 20) {
        pollRef.current = setTimeout(poll, 3000);
      } else {
        setPayState("pending");
        setNotice(
          "We are still waiting for the provider to confirm. This usually takes a minute - refresh in a moment to see it applied.",
        );
      }
    };
    pollRef.current = setTimeout(poll, 1500);

    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [token, refresh]);

  // Default the rail to Bachs when it is available, otherwise to USDT.
  useEffect(() => {
    if (bachsReady && rail !== "bachs" && rail === "crypto" && corridors.length === 0) {
      setRail("bachs");
    }
  }, [bachsReady, rail, corridors.length]);

  useEffect(() => {
    if (!corridor && corridors.length) setCorridor(corridors[0].id);
  }, [corridor, corridors]);

  async function startPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!token || paying) return;
    setPaying(true);
    setActionError(null);
    setNotice(null);
    try {
      const inv = await api<Invoice>("/api/billing/invoices", {
        method: "POST",
        token,
        body: JSON.stringify({
          tier,
          method: rail,
          annual: cycle === "annual",
          promo_code: promoCode.trim() || undefined,
          payment_method: rail === "bachs" ? corridor || undefined : undefined,
        }),
      });

      setPromoCode("");
      await refresh();

      if (inv.checkout_url) {
        // Same-tab so the provider's success_url brings the customer back here.
        window.location.assign(inv.checkout_url);
        return;
      }

      const exact = inv.unique_amount ?? inv.amount_usd;
      setNotice(
        `Invoice created for $${exact.toFixed(2)}. Send exactly that amount using the details below, then submit your reference.`,
      );
      setProofFor(inv);
      setProofValue("");
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setPaying(false);
    }
  }

  async function submitProof() {
    if (!token || !proofFor) return;
    setProofBusy(true);
    setActionError(null);
    try {
      await api(`/api/billing/invoices/${proofFor.id}/tx-ref`, {
        method: "POST",
        token,
        body: JSON.stringify({ tx_ref: proofValue.trim() }),
      });
      setNotice("Payment proof submitted. An admin will verify it and activate your plan.");
      setProofFor(null);
      setProofValue("");
      await refresh();
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setProofBusy(false);
    }
  }

  async function cancelInvoice(id: string) {
    if (!token) return;
    try {
      await api(`/api/billing/invoices/${id}/cancel`, { method: "POST", token });
      setNotice("Invoice cancelled.");
      await refresh();
    } catch (err) {
      setActionError(describeError(err));
    }
  }

  async function toggleAutoRenew() {
    if (!token || !sub || sub.status !== "active") return;
    try {
      await api("/api/billing/subscription/auto-renew", {
        method: "POST",
        token,
        body: JSON.stringify({ enabled: !sub.auto_renew }),
      });
      await refresh();
    } catch (err) {
      setActionError(describeError(err));
    }
  }

  const pendingInvoice = invoices.find((i) => i.status === "pending");
  const exactAmount = (inv: Invoice) => inv.unique_amount ?? inv.amount_usd;
  const currentTier = (sub?.status !== "none" && sub?.tier ? sub.tier : user?.tier ?? "free").toLowerCase();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Billing &amp; Subscription</h1>
        {payState === "returning" && (
          <Badge variant="yellow" dot>Confirming payment</Badge>
        )}
      </div>

      {loadError && <p className="text-sm text-red">{loadError}</p>}
      {actionError && <p className="text-sm text-red">{actionError}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      {/* Current subscription */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard
          label="Current Tier"
          value={currentTier.toUpperCase()}
        />
        <StatCard label="Status" value={(sub?.status ?? "none").toUpperCase()} />
        <StatCard
          label="Days Left"
          value={sub?.days_left != null && (sub.status === "active" || sub.status === "grace") ? `${sub.days_left}` : "-"}
        />
        <StatCard
          label="Lifetime Spend"
          value={sub?.lifetime_spend_usd != null ? `$${sub.lifetime_spend_usd.toLocaleString()}` : "$0"}
        />
      </div>

      {sub?.status === "grace" && sub.grace_until && (
        <Card>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="text-sm font-medium text-yellow">
                Payment grace period - your {sub.tier?.toUpperCase()} plan stays on until{" "}
                {new Date(sub.grace_until).toLocaleDateString()}.
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Settle the renewal invoice to keep signals, alerts and VIP auto-trade running.
              </p>
            </div>
            {pendingInvoice && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  if (pendingInvoice.checkout_url) window.location.assign(pendingInvoice.checkout_url);
                  else { setProofFor(pendingInvoice); setProofValue(""); }
                }}
              >
                Pay Renewal Invoice
              </Button>
            )}
          </div>
        </Card>
      )}

      {sub?.status === "active" && (
        <Card>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="text-sm font-medium">
                {sub.tier?.toUpperCase()} renews {new Date(sub.expires_at!).toLocaleDateString()}
                {sub.cancel_at_period_end && (
                  <span className="text-yellow ml-2">(cancels at period end)</span>
                )}
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Auto-renew creates a reminder invoice before expiry.
              </p>
            </div>
            <Button variant={sub.auto_renew ? "secondary" : "primary"} size="sm" onClick={toggleAutoRenew}>
              Auto-renew: {sub.auto_renew ? "ON" : "OFF"}
            </Button>
          </div>
        </Card>
      )}

      {/* Plans */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Plans</CardTitle></CardHeader>
          <div className="space-y-3">
            {plans.map((p) => {
              const active = p.tier === tier;
              return (
                <button
                  key={p.tier}
                  type="button"
                  onClick={() => setTier(p.tier)}
                  className={clsx(
                    "w-full text-left p-3 rounded-lg border transition-colors",
                    active
                      ? "border-green bg-green/5"
                      : "border-transparent bg-bg-tertiary hover:border-border-light",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-semibold">{p.name}</span>
                      <span className="text-xs text-text-muted ml-2">{p.duration_days} days</span>
                    </div>
                    <span className="font-mono font-bold text-lg">
                      ${p.price_usd}
                      <span className="text-xs text-text-muted font-normal">/mo</span>
                    </span>
                  </div>
                  {p.annual_price_usd ? (
                    <p className="text-xs text-text-muted mt-1">
                      Yearly{" "}
                      <span className="text-green font-mono">${p.annual_price_usd}/yr</span>
                      {p.annual_savings_usd ? ` - save $${p.annual_savings_usd}` : ""}
                    </p>
                  ) : null}
                </button>
              );
            })}
            <p className="text-xs text-text-muted">
              {bachsReady
                ? "Pay by card, bank transfer, mobile money or crypto. USDT and manual bank transfer are available as fallbacks."
                : "Pay by USDT (TRC-20) or request manual bank/card details."}
            </p>
          </div>
        </Card>

        {/* Payment */}
        <Card>
          <CardHeader><CardTitle>Make a payment</CardTitle></CardHeader>
          <form onSubmit={startPayment} className="space-y-4">
            <div className="flex items-center gap-2">
              {(["monthly", "annual"] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCycle(c)}
                  className={clsx(
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                    cycle === c
                      ? "bg-green text-black"
                      : "bg-bg-tertiary text-text-secondary hover:text-text-primary",
                  )}
                >
                  {c === "monthly" ? "Monthly" : "Annual (2 months free)"}
                </button>
              ))}
            </div>

            <div className="rounded-lg bg-bg-tertiary p-3 flex items-baseline justify-between">
              <span className="text-sm text-text-secondary">
                {selectedPlan?.name ?? "Plan"}{" "}
                <span className="text-text-muted">({cycle})</span>
              </span>
              <span className="font-mono font-bold text-lg">${price.toFixed(2)}</span>
            </div>

            {bachsReady && corridors.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-text-secondary">How would you like to pay?</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {corridors.map((c) => {
                    const active = rail === "bachs" && corridor === c.id;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => { setRail("bachs"); setCorridor(c.id); }}
                        className={clsx(
                          "flex items-start gap-3 p-3 rounded-lg border text-left transition-colors",
                          active
                            ? "border-green bg-green/5"
                            : "border-border bg-bg-tertiary hover:border-border-light",
                        )}
                      >
                        <RailIcon kind={c.kind} className={clsx("mt-0.5 shrink-0", active ? "text-green" : "text-text-muted")} />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium text-text-primary">{c.label}</span>
                          <span className="block text-xs text-text-muted">{c.currency}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <details className="group">
              <summary className="cursor-pointer text-sm text-text-secondary hover:text-text-primary select-none">
                Other ways to pay
              </summary>
              <div className="mt-3 space-y-2">
                {(
                  [
                    { id: "crypto" as const, label: "USDT (TRC-20)", hint: "Send to our wallet, then submit the transaction hash" },
                    { id: "manual" as const, label: "Manual bank or card transfer", hint: "We send you the account details" },
                  ]
                ).map((r) => {
                  const active = rail === r.id;
                  return (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setRail(r.id)}
                      className={clsx(
                        "w-full text-left p-3 rounded-lg border transition-colors",
                        active
                          ? "border-green bg-green/5"
                          : "border-border bg-bg-tertiary hover:border-border-light",
                      )}
                    >
                      <span className="block text-sm font-medium text-text-primary">{r.label}</span>
                      <span className="block text-xs text-text-muted mt-0.5">{r.hint}</span>
                    </button>
                  );
                })}
              </div>
            </details>

            <Input
              label="Promo code (optional)"
              value={promoCode}
              onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
              placeholder="SAVE20"
              maxLength={40}
            />

            <Button type="submit" disabled={paying} className="w-full">
              {paying
                ? "Starting checkout..."
                : rail === "bachs"
                  ? `Pay $${price.toFixed(2)} securely`
                  : `Create invoice for $${price.toFixed(2)}`}
            </Button>

            {rail === "bachs" && (
              <p className="text-xs text-text-muted text-center">
                You will be taken to our payment provider&apos;s secure page to complete the payment.
              </p>
            )}
          </form>
        </Card>
      </div>

      {/* Plan comparison */}
      <Card padding={false}>
        <div className="flex items-center justify-between gap-3 px-4 pt-4">
          <CardTitle>Compare Plans</CardTitle>
          <Badge variant={tierBadgeVariant(currentTier)}>
            Current: {tierLabel(currentTier)}
          </Badge>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs text-text-muted px-4 py-2 font-medium">Feature</th>
                <th className="text-center text-xs text-text-muted px-4 py-2 font-medium">Free</th>
                <th className="text-center text-xs text-text-muted px-4 py-2 font-medium">Premium</th>
                <th className="text-center text-xs text-text-muted px-4 py-2 font-medium">VIP</th>
              </tr>
            </thead>
            <tbody>
              {FEATURE_MATRIX.map((f) => (
                <tr key={f.label} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5">{f.label}</td>
                  <td className="px-4 py-2.5 text-center"><FeatureCell value={f.free} /></td>
                  <td className="px-4 py-2.5 text-center"><FeatureCell value={f.premium} /></td>
                  <td className="px-4 py-2.5 text-center"><FeatureCell value={f.vip} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Invoices */}
      <Card padding={false}>
        <div className="px-4 pt-4"><CardTitle>My invoices</CardTitle></div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="px-4 py-2 font-medium">Plan</th>
                <th className="px-4 py-2 font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Paid with</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-text-muted">No invoices yet.</td>
                </tr>
              )}
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5 capitalize">
                    {inv.tier}
                    {inv.promo_code && <span className="text-xs text-purple ml-1">({inv.promo_code})</span>}
                  </td>
                  <td className="px-4 py-2.5 font-mono">
                    ${inv.amount_usd.toLocaleString()}
                    {inv.discount_usd > 0 && (
                      <span className="text-xs text-green ml-1 line-through">
                        ${(inv.amount_usd + inv.discount_usd).toLocaleString()}
                      </span>
                    )}
                    {inv.status === "pending" && inv.unique_amount != null && (
                      <span className="block text-xs text-yellow font-normal">
                        send exactly ${inv.unique_amount.toFixed(2)}
                      </span>
                    )}
                    {inv.status === "pending" && inv.memo && (
                      <span className="block text-xs text-text-muted font-normal">ref {inv.memo}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">{corridorLabel(inv)}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={STATUS_VARIANT[inv.status] ?? "gray"}>{inv.status}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-muted">
                    {new Date(inv.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    {inv.status === "pending" && (
                      <div className="flex gap-2">
                        {inv.checkout_url ? (
                          <Button size="sm" variant="primary" onClick={() => window.location.assign(inv.checkout_url!)}>
                            Pay now
                          </Button>
                        ) : (
                          <Button size="sm" variant="secondary" onClick={() => { setProofFor(inv); setProofValue(""); }}>
                            Submit proof
                          </Button>
                        )}
                        <Button size="sm" variant="danger" onClick={() => cancelInvoice(inv.id)}>
                          Cancel
                        </Button>
                      </div>
                    )}
                    {inv.status === "approved" && inv.wallet_address && (
                      <button
                        className="text-xs text-blue hover:underline"
                        onClick={() => setNotice(`Wallet: ${inv.wallet_address}`)}
                      >
                        wallet info
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Payment proof */}
      <Modal open={!!proofFor} onClose={() => setProofFor(null)} title="Submit payment proof">
        {proofFor && (
          <div className="space-y-4">
            {proofFor.wallet_address ? (
              <div className="space-y-2 text-sm">
                <p className="text-text-secondary">
                  Send exactly{" "}
                  <span className="font-bold font-mono">${exactAmount(proofFor).toFixed(2)}</span>{" "}
                  USDT on <span className="uppercase">{(proofFor.network || "").replace("usdt_", "")}</span> to:
                </p>
                <code className="block bg-bg-tertiary rounded p-2 text-xs break-all">{proofFor.wallet_address}</code>
                {proofFor.memo && (
                  <p className="text-xs text-text-muted">
                    Use <span className="font-mono font-medium">{proofFor.memo}</span> as the transfer reference.
                  </p>
                )}
              </div>
            ) : bankCard?.account_name || bankCard?.account_number ? (
              <div className="space-y-2 text-sm">
                <p className="text-text-secondary">
                  Pay <span className="font-bold font-mono">${exactAmount(proofFor).toFixed(2)}</span> by bank
                  transfer or card to:
                </p>
                <div className="space-y-1 bg-bg-tertiary rounded p-3 text-xs">
                  {bankCard.bank_name && (
                    <p><span className="text-text-muted">Bank:</span> <span className="font-medium">{bankCard.bank_name}</span></p>
                  )}
                  {bankCard.account_name && (
                    <p><span className="text-text-muted">Account name:</span> <span className="font-medium">{bankCard.account_name}</span></p>
                  )}
                  {bankCard.account_number && (
                    <p><span className="text-text-muted">Account number:</span> <span className="font-medium font-mono">{bankCard.account_number}</span></p>
                  )}
                  {bankCard.branch && (
                    <p><span className="text-text-muted">Branch:</span> <span className="font-medium">{bankCard.branch}</span></p>
                  )}
                  {bankCard.instructions && (
                    <p className="pt-1 border-t border-border mt-1 text-text-secondary">{bankCard.instructions}</p>
                  )}
                </div>
                {proofFor.memo && (
                  <p className="text-xs text-text-muted">
                    Use <span className="font-mono font-medium">{proofFor.memo}</span> as the transfer reference.
                  </p>
                )}
              </div>
            ) : (
              <p className="text-text-secondary text-sm">
                Manual payment: DM @Johnpaulmuna_83 for the bank/card details, then enter the reference below.
              </p>
            )}

            <Input
              label="Transaction hash or reference"
              value={proofValue}
              onChange={(e) => setProofValue(e.target.value)}
              minLength={4}
              required
            />
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" onClick={() => setProofFor(null)}>Close</Button>
              <Button onClick={submitProof} disabled={proofBusy || proofValue.trim().length < 4}>
                {proofBusy ? "Submitting..." : "Submit proof"}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
