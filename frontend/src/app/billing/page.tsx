"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
interface BankCard { bank_name: string; account_name: string; account_number: string; branch: string; instructions: string }

const GATEWAY_LABELS: Record<string, string> = {
  nowpayments: "Crypto checkout (NOWPayments)",
  stripe: "Card (Stripe)",
  paystack: "Paystack (card/transfer)",
  flutterwave: "Flutterwave (card/transfer)",
};

const STATUS_VARIANT: Record<string, "green" | "red" | "yellow" | "gray" | "blue"> = {
  approved: "green", pending: "yellow", rejected: "red", refunded: "blue",
  cancelled: "gray", expired: "gray",
};

function providerLabel(inv: Invoice): string {
  if (inv.provider && GATEWAY_LABELS[inv.provider]) return GATEWAY_LABELS[inv.provider];
  if (inv.provider === "crypto") return `USDT ${inv.network?.replace("usdt_", "").toUpperCase() || ""}`.trim();
  if (inv.provider === "manual") return "Manual";
  return inv.method;
}

export default function BillingPage() {
  const { token, user } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [gateways, setGateways] = useState<string[]>([]);
  const [bankCard, setBankCard] = useState<BankCard | null>(null);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // invoice form
  const [tier, setTier] = useState("premium");
  const [method, setMethod] = useState("crypto");
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [promoCode, setPromoCode] = useState("");
  const [creating, setCreating] = useState(false);
  // tx ref modal-ish state
  const [txFor, setTxFor] = useState<string | null>(null);
  const [txValue, setTxValue] = useState("");
  // hosted checkout redirect (gateway invoices)
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    const [plansRes, subRes, invRes] = await Promise.allSettled([
      api<{ plans: Plan[]; bank_card?: BankCard; gateways?: string[] }>("/api/billing/plans", { token }),
      api<Subscription>("/api/billing/subscription", { token }),
      api<Invoice[]>("/api/billing/invoices", { token }),
    ]);

    // Each panel is independent: one failing endpoint must not blank the page.
    const failed: string[] = [];

    if (plansRes.status === "fulfilled") {
      setPlans(plansRes.value?.plans ?? []);
      setBankCard(plansRes.value?.bank_card ?? null);
      setGateways(plansRes.value?.gateways ?? []);
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

    setError(
      failed.length
        ? `Could not load ${failed.join(", ")} - the rest of billing data is still available.`
        : null
    );
  }, [token]);

  useEffect(() => {
    if (!token) return;
    refresh();
  }, [token, refresh]);

  async function createInvoice(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setCreating(true); setError(null); setNotice(null);
    try {
      const inv = await api<Invoice>("/api/billing/invoices", {
        method: "POST", token,
        body: JSON.stringify({
          tier, method, annual: cycle === "annual",
          promo_code: promoCode.trim() || undefined,
        }),
      });
      if (inv.checkout_url) {
        setCheckoutUrl(inv.checkout_url);
        setNotice("Invoice created - continue to the secure checkout to pay.");
      } else {
        setNotice(`Invoice created - send $${inv.unique_amount ?? inv.amount_usd} then submit the transaction reference below.`);
      }
      setPromoCode("");
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not create invoice";
      setError(msg === "checkout_unavailable"
        ? "That payment provider is unavailable right now - try again, or pick another method."
        : msg);
    } finally {
      setCreating(false);
    }
  }

  async function submitTx() {
    if (!token || !txFor) return;
    try {
      await api(`/api/billing/invoices/${txFor}/tx-ref`, { method: "POST", token, body: JSON.stringify({ tx_ref: txValue }) });
      setNotice("Payment proof submitted - an admin will verify it shortly.");
      setTxFor(null); setTxValue("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    }
  }

  async function cancelInvoice(id: string) {
    if (!token) return;
    try {
      await api(`/api/billing/invoices/${id}/cancel`, { method: "POST", token });
      setNotice("Invoice cancelled");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  async function toggleAutoRenew() {
    if (!token || !sub || sub.status !== "active") return;
    try {
      await api("/api/billing/subscription/auto-renew", {
        method: "POST", token, body: JSON.stringify({ enabled: !sub?.auto_renew }),
      });
      await refresh();
    } catch { /* no sub */ }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Billing & Subscription</h1>

      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      {checkoutUrl && (
        <Card>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="text-sm font-medium">Complete your payment on the secure checkout page.</p>
              <p className="text-xs text-text-muted mt-0.5">
                Your invoice approves automatically once the provider confirms it.
              </p>
            </div>
            <div className="flex gap-2">
              <a href={checkoutUrl} target="_blank" rel="noopener noreferrer">
                <Button variant="primary" size="sm">Continue to Payment</Button>
              </a>
              <Button variant="secondary" size="sm" onClick={() => setCheckoutUrl(null)}>Dismiss</Button>
            </div>
          </div>
        </Card>
      )}

      {/* Current subscription */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard label="Current Tier" value={(sub?.status !== "none" && sub?.tier ? sub.tier : user?.tier ?? "free").toUpperCase()} />
        <StatCard label="Status" value={(sub?.status ?? "none").toUpperCase()} />
        <StatCard label="Days Left" value={sub?.days_left != null && (sub.status === "active" || sub.status === "grace") ? `${sub.days_left}` : "-"} />
        <StatCard label="Lifetime Spend" value={sub?.lifetime_spend_usd != null ? `$${sub.lifetime_spend_usd.toLocaleString()}` : "$0"} />
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
            {sub.auto_renew && (
              <Button variant="primary" size="sm" onClick={() => {
                const pending = invoices.find((i) => i.status === "pending");
                if (pending?.checkout_url) window.open(pending.checkout_url, "_blank", "noopener");
                else if (pending) setTxFor(pending.id);
              }}>
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
              <p className="text-xs text-text-muted mt-0.5">Auto-renew creates a reminder invoice before expiry.</p>
            </div>
            <Button variant={sub.auto_renew ? "secondary" : "primary"} size="sm" onClick={toggleAutoRenew}>
              Auto-renew: {sub.auto_renew ? "ON" : "OFF"}
            </Button>
          </div>
        </Card>
      )}

      {/* Plans + new invoice */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Plans</CardTitle></CardHeader>
          <div className="space-y-3">
            {(plans||[]).map((p) => (
              <div key={p.tier} className="p-3 bg-bg-tertiary rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold">{p.name}</span>
                    <span className="text-xs text-text-muted ml-2">{p.duration_days} days</span>
                  </div>
                  <span className="font-mono font-bold text-lg">${p.price_usd}<span className="text-xs text-text-muted font-normal">/mo</span></span>
                </div>
                {p.annual_price_usd ? (
                  <p className="text-xs text-text-muted mt-1">
                    Yearly <span className="text-green font-mono">${p.annual_price_usd}/yr</span>
                    {p.annual_savings_usd ? ` - save $${p.annual_savings_usd}` : ""}
                  </p>
                ) : null}
              </div>
            ))}
            <p className="text-xs text-text-muted">
              {gateways.length > 0
                ? `Pay by ${gateways.map((g) => GATEWAY_LABELS[g] ?? g).join(", ")}, USDT (TRC-20), or manual bank/card.`
                : "Pay in USDT (TRC-20) or request manual bank/card details."}
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader><CardTitle>New Invoice</CardTitle></CardHeader>
          <form onSubmit={createInvoice} className="space-y-4">
            <div className="flex items-center gap-2">
              {(["monthly", "annual"] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCycle(c)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    cycle === c ? "bg-green text-black" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {c === "monthly" ? "Monthly" : "Annual (save 2 months)"}
                </button>
              ))}
            </div>
            <Select
              label="Tier"
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              options={plans.map((p) => ({
                value: p.tier,
                label: cycle === "annual" && p.annual_price_usd
                  ? `${p.name} - $${p.annual_price_usd}/yr`
                  : `${p.name} - $${p.price_usd}/mo`,
              }))}
            />
            <Select
              label="Method"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              options={[
                { value: "crypto", label: "Crypto (USDT)" },
                { value: "manual", label: "Manual (bank/card)" },
                ...gateways.map((g) => ({ value: g, label: GATEWAY_LABELS[g] ?? g })),
              ]}
            />
            <Input
              label="Promo Code (optional)"
              value={promoCode}
              onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
              placeholder="SAVE20"
            />
            <Button type="submit" disabled={creating} className="w-full">
              {creating ? "Creating..." : "Create Invoice"}
            </Button>
          </form>
        </Card>
      </div>

      {/* My invoices */}
      <Card padding={false}>
        <div className="px-4 pt-4"><CardTitle>My Invoices</CardTitle></div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm min-w-[540px]">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="px-4 py-2 font-medium">Tier</th>
                <th className="px-4 py-2 font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Method</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-text-muted">No invoices yet.</td></tr>
              )}
              {(invoices||[]).map((inv) => (
                <tr key={inv.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5 capitalize">{inv.tier}{inv.promo_code && <span className="text-xs text-purple ml-1">({inv.promo_code})</span>}</td>
                  <td className="px-4 py-2.5 font-mono">
                    ${inv.amount_usd.toLocaleString()}
                    {inv.discount_usd > 0 && <span className="text-xs text-green ml-1 line-through">${(inv.amount_usd + inv.discount_usd).toLocaleString()}</span>}
                    {inv.status === "pending" && inv.unique_amount != null && (
                      <span className="block text-xs text-yellow font-normal">send exactly ${inv.unique_amount.toFixed(2)}</span>
                    )}
                    {inv.status === "pending" && inv.memo && (
                      <span className="block text-xs text-text-muted font-normal">ref {inv.memo}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">{providerLabel(inv)}</td>
                  <td className="px-4 py-2.5"><Badge variant={STATUS_VARIANT[inv.status] ?? "gray"}>{inv.status}</Badge></td>
                  <td className="px-4 py-2.5 text-xs text-text-muted">{new Date(inv.created_at).toLocaleString()}</td>
                  <td className="px-4 py-2.5">
                    {inv.status === "pending" && (
                      <div className="flex gap-2">
                        {inv.checkout_url ? (
                          <Button size="sm" variant="primary" onClick={() => window.open(inv.checkout_url!, "_blank", "noopener")}>
                            Pay Now
                          </Button>
                        ) : (
                          <Button size="sm" variant="secondary" onClick={() => { setTxFor(inv.id); setTxValue(""); }}>Submit Proof</Button>
                        )}
                        <Button size="sm" variant="danger" onClick={() => cancelInvoice(inv.id)}>Cancel</Button>
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

      {/* Pending payment instructions */}
      {txFor && (
        <Card>
          <CardHeader><CardTitle>Submit Payment Proof</CardTitle></CardHeader>
          {(() => {
            const inv = invoices.find((i) => i.id === txFor);
            const exact = inv ? (inv.unique_amount ?? inv.amount_usd) : 0;
            const refLine = inv?.memo && (
              <p className="text-xs text-text-muted">
                Use <span className="font-mono font-medium">{inv.memo}</span> as the transfer reference/memo.
              </p>
            );
            return inv?.wallet_address ? (
              <div className="space-y-2 mb-4 text-sm">
                <p className="text-text-secondary">Send exactly <span className="font-bold font-mono">${exact.toFixed(2)}</span> USDT on <span className="uppercase">{inv.network?.replace("usdt_", "")}</span> to:</p>
                <code className="block bg-bg-tertiary rounded p-2 text-xs break-all">{inv.wallet_address}</code>
                {refLine}
              </div>
            ) : (
              <div className="space-y-2 mb-4 text-sm">
                {bankCard?.account_name || bankCard?.account_number ? (
                  <>
                    <p className="text-text-secondary">Pay <span className="font-bold font-mono">${exact.toFixed(2)}</span> via bank transfer or card to:</p>
                    <div className="space-y-1 bg-bg-tertiary rounded p-3 text-xs">
                      {bankCard.bank_name && <p><span className="text-text-muted">Bank:</span> <span className="font-medium">{bankCard.bank_name}</span></p>}
                      {bankCard.account_name && <p><span className="text-text-muted">Account name:</span> <span className="font-medium">{bankCard.account_name}</span></p>}
                      {bankCard.account_number && <p><span className="text-text-muted">Account number:</span> <span className="font-medium font-mono">{bankCard.account_number}</span></p>}
                      {bankCard.branch && <p><span className="text-text-muted">Branch:</span> <span className="font-medium">{bankCard.branch}</span></p>}
                      {bankCard.instructions && <p className="pt-1 border-t border-border mt-1 text-text-secondary">{bankCard.instructions}</p>}
                    </div>
                    {refLine}
                  </>
                ) : (
                  <p className="text-text-secondary">Manual payment: DM @Johnpaulmuna_83 for bank/card details, then enter the reference here.</p>
                )}
              </div>
            );
          })()}
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <Input label="Transaction hash / reference" value={txValue} onChange={(e) => setTxValue(e.target.value)} minLength={4} required />
            <div className="flex gap-2">
              <Button onClick={submitTx}>Submit</Button>
              <Button variant="secondary" onClick={() => setTxFor(null)}>Close</Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
