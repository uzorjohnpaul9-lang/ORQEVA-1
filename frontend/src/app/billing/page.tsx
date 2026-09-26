"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Plan { tier: string; name: string; price_usd: number; duration_days: number }
interface BankCard { bank_name: string; account_name: string; account_number: string; branch: string; instructions: string }
interface Sub {
  tier?: string; status: string; auto_renew?: boolean;
  started_at?: string; expires_at?: string; days_left?: number; lifetime_spend_usd?: number;
}
interface Invoice {
  id: string; tier: string; method: string; network: string | null;
  wallet_address: string | null; amount_usd: number; discount_usd: number;
  promo_code: string | null; status: string; tx_ref: string | null;
  created_at: string; expires_at: string; user_email?: string;
}

const STATUS_VARIANT: Record<string, "green" | "red" | "yellow" | "gray" | "blue"> = {
  approved: "green", pending: "yellow", rejected: "red", refunded: "blue", cancelled: "gray",
};

export default function BillingPage() {
  const { token, user } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [bankCard, setBankCard] = useState<BankCard | null>(null);
  const [sub, setSub] = useState<Sub | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // invoice form
  const [tier, setTier] = useState("premium");
  const [method, setMethod] = useState("crypto");
  const [promoCode, setPromoCode] = useState("");
  const [creating, setCreating] = useState(false);
  // tx ref modal-ish state
  const [txFor, setTxFor] = useState<string | null>(null);
  const [txValue, setTxValue] = useState("");

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [p, s, inv] = await Promise.all([
        api<{ plans: Plan[]; bank_card?: BankCard }>("/api/billing/plans", { token }),
        api<Sub>("/api/billing/subscription", { token }),
        api<Invoice[]>("/api/billing/invoices", { token }),
      ]);
      setPlans(p.plans);
      setBankCard(p.bank_card ?? null);
      setSub(s);
      setInvoices(inv);
      setError(null);
    } catch {
      setError("Could not load billing data");
    }
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
        body: JSON.stringify({ tier, method, promo_code: promoCode.trim() || undefined }),
      });
      setNotice(`Invoice created - send $${inv.amount_usd} then submit the transaction reference below.`);
      setPromoCode("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create invoice");
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

      {/* Current subscription */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard label="Current Tier" value={(sub?.status !== "none" && sub?.tier ? sub.tier : user?.tier ?? "free").toUpperCase()} />
        <StatCard label="Status" value={(sub?.status ?? "none").toUpperCase()} />
        <StatCard label="Days Left" value={sub?.days_left != null && sub.status === "active" ? `${sub.days_left}` : "-"} />
        <StatCard label="Lifetime Spend" value={sub?.lifetime_spend_usd != null ? `$${sub.lifetime_spend_usd.toLocaleString()}` : "$0"} />
      </div>

      {sub?.status === "active" && (
        <Card>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="text-sm font-medium">
                {sub.tier?.toUpperCase()} renews {new Date(sub.expires_at!).toLocaleDateString()}
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
            {plans.map((p) => (
              <div key={p.tier} className="flex items-center justify-between p-3 bg-bg-tertiary rounded-lg">
                <div>
                  <span className="font-semibold">{p.name}</span>
                  <span className="text-xs text-text-muted ml-2">{p.duration_days} days</span>
                </div>
                <span className="font-mono font-bold text-lg">${p.price_usd}<span className="text-xs text-text-muted font-normal">/mo</span></span>
              </div>
            ))}
            <p className="text-xs text-text-muted">Pay in USDT (TRC-20) or request manual bank/card details.</p>
          </div>
        </Card>

        <Card>
          <CardHeader><CardTitle>New Invoice</CardTitle></CardHeader>
          <form onSubmit={createInvoice} className="space-y-4">
            <Select
              label="Tier"
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              options={plans.map((p) => ({ value: p.tier, label: `${p.name} - $${p.price_usd}/mo` }))}
            />
            <Select
              label="Method"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              options={[{ value: "crypto", label: "Crypto (USDT)" }, { value: "manual", label: "Manual (bank/card)" }]}
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
          <table className="w-full text-sm">
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
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5 capitalize">{inv.tier}{inv.promo_code && <span className="text-xs text-purple ml-1">({inv.promo_code})</span>}</td>
                  <td className="px-4 py-2.5 font-mono">
                    ${inv.amount_usd.toLocaleString()}
                    {inv.discount_usd > 0 && <span className="text-xs text-green ml-1 line-through">${(inv.amount_usd + inv.discount_usd).toLocaleString()}</span>}
                  </td>
                  <td className="px-4 py-2.5">{inv.method === "crypto" ? `USDT ${inv.network?.replace("usdt_", "").toUpperCase()}` : "Manual"}</td>
                  <td className="px-4 py-2.5"><Badge variant={STATUS_VARIANT[inv.status] ?? "gray"}>{inv.status}</Badge></td>
                  <td className="px-4 py-2.5 text-xs text-text-muted">{new Date(inv.created_at).toLocaleString()}</td>
                  <td className="px-4 py-2.5">
                    {inv.status === "pending" && (
                      <div className="flex gap-2">
                        <Button size="sm" variant="secondary" onClick={() => { setTxFor(inv.id); setTxValue(""); }}>Submit Proof</Button>
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
            return inv?.wallet_address ? (
              <div className="space-y-2 mb-4 text-sm">
                <p className="text-text-secondary">Send exactly <span className="font-bold font-mono">${inv.amount_usd}</span> USDT on <span className="uppercase">{inv.network?.replace("usdt_", "")}</span> to:</p>
                <code className="block bg-bg-tertiary rounded p-2 text-xs break-all">{inv.wallet_address}</code>
              </div>
            ) : (
              <div className="space-y-2 mb-4 text-sm">
                {bankCard?.account_name || bankCard?.account_number ? (
                  <>
                    <p className="text-text-secondary">Pay <span className="font-bold font-mono">${inv?.amount_usd}</span> via bank transfer or card to:</p>
                    <div className="space-y-1 bg-bg-tertiary rounded p-3 text-xs">
                      {bankCard.bank_name && <p><span className="text-text-muted">Bank:</span> <span className="font-medium">{bankCard.bank_name}</span></p>}
                      {bankCard.account_name && <p><span className="text-text-muted">Account name:</span> <span className="font-medium">{bankCard.account_name}</span></p>}
                      {bankCard.account_number && <p><span className="text-text-muted">Account number:</span> <span className="font-medium font-mono">{bankCard.account_number}</span></p>}
                      {bankCard.branch && <p><span className="text-text-muted">Branch:</span> <span className="font-medium">{bankCard.branch}</span></p>}
                      {bankCard.instructions && <p className="pt-1 border-t border-border mt-1 text-text-secondary">{bankCard.instructions}</p>}
                    </div>
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
