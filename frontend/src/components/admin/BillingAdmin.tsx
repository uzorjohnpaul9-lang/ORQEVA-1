"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { Invoice, RevenueDashboard } from "@/lib/types";
import { AdminCard, AdminCardHeader, AdminCardTitle, AdminStatCard } from "@/components/admin/AdminCard";

interface Promo { code: string; discount_pct: number; max_uses: number; uses_count: number; active: boolean }
interface BankCard {
  bank_name: string; account_name: string; account_number: string;
  branch: string; instructions: string;
}
interface Stats {
  revenue_usd: number; refunded_usd: number; net_usd: number;
  pending_invoices: number; approved_invoices: number;
  active_subscriptions: number;
  revenue_by_tier: Record<string, { count: number; revenue_usd: number }>;
}

const STATUS_VARIANT: Record<string, "green" | "red" | "yellow" | "gray" | "blue"> = {
  approved: "green", pending: "yellow", rejected: "red", refunded: "blue",
  cancelled: "gray", expired: "gray",
};

export function BillingAdmin({ token }: { token: string }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [revenue, setRevenue] = useState<RevenueDashboard | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [promos, setPromos] = useState<Promo[]>([]);
  const [newPromo, setNewPromo] = useState({ code: "", discount_pct: "20", max_uses: "100" });
  const [bank, setBank] = useState<BankCard>({ bank_name: "", account_name: "", account_number: "", branch: "", instructions: "" });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [st, rev, all, pr] = await Promise.all([
        api<Stats>("/api/billing/admin/stats", { token }),
        api<RevenueDashboard>("/api/billing/admin/revenue", { token }),
        api<Invoice[]>("/api/billing/admin/invoices?limit=50", { token }),
        api<Promo[]>("/api/billing/admin/promos", { token }),
      ]);
      setStats(st); setRevenue(rev); setInvoices(all); setPromos(pr); setError(null);
    } catch {
      setError("Could not load admin billing data");
    }
  }, [token]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (!token) return;
    api<BankCard>("/api/billing/admin/payment-details", { token })
      .then((b) => setBank({ bank_name: b.bank_name ?? "", account_name: b.account_name ?? "", account_number: b.account_number ?? "", branch: b.branch ?? "", instructions: b.instructions ?? "" }))
      .catch(() => { /* keep defaults */ });
  }, [token]);

  async function saveBank(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/api/billing/admin/payment-details", {
        method: "PUT", token,
        body: JSON.stringify(bank),
      });
      setNotice("Payment details saved"); setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function action(id: string, kind: "approve" | "reject" | "refund") {
    try {
      await api(`/api/billing/admin/invoices/${id}/${kind}`, {
        method: "POST", token, body: JSON.stringify({ reason: kind }),
      });
      setNotice(`Invoice ${kind}ed`); setError(null); await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${kind} failed`);
    }
  }

  async function createPromo(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/api/billing/admin/promos", {
        method: "POST", token,
        body: JSON.stringify({
          code: newPromo.code,
          discount_pct: Number(newPromo.discount_pct),
          max_uses: Number(newPromo.max_uses),
        }),
      });
      setNewPromo({ code: "", discount_pct: "20", max_uses: "100" });
      setNotice("Promo created"); setError(null); await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promo creation failed");
    }
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <AdminStatCard label="Revenue" value={stats ? `$${stats.revenue_usd.toLocaleString()}` : "-"} />
        <AdminStatCard label="Refunded" value={stats ? `$${stats.refunded_usd.toLocaleString()}` : "-"} />
        <AdminStatCard label="Pending Invoices" value={stats ? `${stats.pending_invoices}` : "-"} />
        <AdminStatCard label="Active Subs" value={stats ? `${stats.active_subscriptions}` : "-"} />
      </div>

      {stats && stats.revenue_by_tier && Object.keys(stats.revenue_by_tier).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.revenue_by_tier).map(([tier, agg]) => (
            <div key={tier} className="px-3 py-2 bg-bg-tertiary rounded-lg text-sm">
              <span className="uppercase text-text-muted">{tier}</span>{" "}
              <span className="font-semibold">${agg.revenue_usd.toLocaleString()}</span>
              <span className="text-xs text-text-muted"> ({agg.count})</span>
            </div>
          ))}
        </div>
      )}

      {revenue && (
        <AdminCard>
          <AdminCardHeader>
            <AdminCardTitle>Revenue Dashboard</AdminCardTitle>
          </AdminCardHeader>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <AdminStatCard label="MRR" value={`$${revenue.mrr_usd.toLocaleString()}`} />
            <AdminStatCard label="ARR" value={`$${revenue.arr_usd.toLocaleString()}`} />
            <AdminStatCard label="Net (30d-refunds)" value={`$${revenue.net_usd.toLocaleString()}`} />
            <AdminStatCard label="Paying Users" value={`${revenue.paying_users}`} />
            <AdminStatCard label="Avg LTV" value={`$${revenue.ltv_usd.toLocaleString()}`} />
            <AdminStatCard label="Churned (30d)" value={`${revenue.churned_30d}`} />
          </div>

          <div className="flex flex-wrap gap-2 mt-4 text-sm">
            <span className="px-3 py-2 bg-bg-tertiary rounded-lg">Expiring 7d: <b>{revenue.expiring_7d}</b></span>
            <span className="px-3 py-2 bg-bg-tertiary rounded-lg">Expiring 3d: <b>{revenue.expiring_3d}</b></span>
            <span className="px-3 py-2 bg-bg-tertiary rounded-lg">Expiring 1d: <b>{revenue.expiring_1d}</b></span>
            <span className="px-3 py-2 bg-bg-tertiary rounded-lg">In grace: <b>{revenue.in_grace}</b></span>
            <span className="px-3 py-2 bg-bg-tertiary rounded-lg">Cancelling: <b>{revenue.cancelling_at_period_end}</b></span>
          </div>

          {revenue.revenue_by_month.length > 0 && (() => {
            const peak = Math.max(...revenue.revenue_by_month.map((m) => m.revenue_usd), 1);
            return (
              <div className="mt-4 space-y-1.5">
                <p className="text-xs font-medium text-text-muted uppercase">Revenue by month</p>
                {revenue.revenue_by_month.map((m) => (
                  <div key={m.month} className="flex items-center gap-2 text-xs">
                    <span className="w-16 text-text-muted font-mono">{m.month}</span>
                    <div className="flex-1 bg-bg-tertiary rounded h-3 overflow-hidden">
                      <div
                        className="h-3 bg-green/60 rounded"
                        style={{ width: `${Math.max((m.revenue_usd / peak) * 100, m.revenue_usd > 0 ? 3 : 0)}%` }}
                      />
                    </div>
                    <span className="w-20 text-right font-mono">${m.revenue_usd.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            );
          })()}

          {Object.keys(revenue.revenue_by_provider).length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4 text-sm">
              {Object.entries(revenue.revenue_by_provider).map(([prov, agg]) => (
                <div key={prov} className="px-3 py-2 bg-bg-tertiary rounded-lg">
                  <span className="uppercase text-text-muted">{prov}</span>{" "}
                  <span className="font-semibold">${agg.revenue_usd.toLocaleString()}</span>
                  <span className="text-xs text-text-muted"> ({agg.count})</span>
                </div>
              ))}
            </div>
          )}
        </AdminCard>
      )}

      <AdminCard>
        <AdminCardHeader><AdminCardTitle>Payment Details (shown on invoices)</AdminCardTitle></AdminCardHeader>
        <form onSubmit={saveBank} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input label="Bank name" value={bank.bank_name} onChange={(e) => setBank((b) => ({ ...b, bank_name: e.target.value }))} placeholder="e.g. UBA" />
          <Input label="Account name" value={bank.account_name} onChange={(e) => setBank((b) => ({ ...b, account_name: e.target.value }))} placeholder="e.g. John Paul Muna" />
          <Input label="Account number" value={bank.account_number} onChange={(e) => setBank((b) => ({ ...b, account_number: e.target.value }))} placeholder="e.g. 1234567890" />
          <Input label="Branch" value={bank.branch} onChange={(e) => setBank((b) => ({ ...b, branch: e.target.value }))} placeholder="e.g. Lagos" />
          <div className="sm:col-span-2 space-y-1.5">
            <label className="block text-sm font-medium text-text-secondary">Payment instructions</label>
            <textarea
              className="w-full bg-bg-tertiary border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-green/50 focus:ring-1 focus:ring-green/20 transition-colors"
              rows={3}
              value={bank.instructions}
              onChange={(e) => setBank((b) => ({ ...b, instructions: e.target.value }))}
              placeholder="e.g. Use your invoice ID as reference, then submit proof below."
            />
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" className="w-full sm:w-auto">Save Payment Details</Button>
          </div>
        </form>
      </AdminCard>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Create Promo</AdminCardTitle></AdminCardHeader>
          <form onSubmit={createPromo} className="space-y-3">
            <Input label="Code" value={newPromo.code} onChange={(e) => setNewPromo((p) => ({ ...p, code: e.target.value.toUpperCase() }))} required minLength={3} />
            <Input label="Discount %" type="number" min="1" max="100" value={newPromo.discount_pct} onChange={(e) => setNewPromo((p) => ({ ...p, discount_pct: e.target.value }))} required />
            <Input label="Max Uses" type="number" min="1" value={newPromo.max_uses} onChange={(e) => setNewPromo((p) => ({ ...p, max_uses: e.target.value }))} required />
            <Button type="submit" className="w-full">Create Promo</Button>
          </form>
          <div className="mt-4 space-y-2 border-t border-border pt-3">
            {promos.map((p) => (
              <div key={p.code} className="flex items-center justify-between text-sm">
                <div>
                  <span className="font-mono">{p.code}</span>
                  <span className="text-xs text-text-muted ml-2">{p.discount_pct}% · {p.uses_count}/{p.max_uses}</span>
                </div>
                <Badge variant={p.active ? "green" : "gray"}>{p.active ? "active" : "off"}</Badge>
              </div>
            ))}
            {promos.length === 0 && <p className="text-xs text-text-muted">No promo codes yet.</p>}
          </div>
        </AdminCard>

        <AdminCard className="lg:col-span-2" padding={false}>
          <div className="px-4 pt-4"><AdminCardTitle>All Invoices</AdminCardTitle></div>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="border-b border-purple/25 text-left text-text-muted">
                  <th className="px-4 py-2 font-medium">User</th>
                  <th className="px-4 py-2 font-medium">Tier</th>
                  <th className="px-4 py-2 font-medium">Amount</th>
                  <th className="px-4 py-2 font-medium">Provider</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Proof</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-6 text-center text-text-muted">No invoices.</td></tr>
                )}
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5 text-xs">{inv.user_email ?? "-"}</td>
                    <td className="px-4 py-2.5 capitalize">{inv.tier}</td>
                    <td className="px-4 py-2.5 font-mono">
                      ${inv.amount_usd.toLocaleString()}
                      {inv.status === "pending" && inv.unique_amount != null && (
                        <span className="block text-xs text-yellow font-normal">${inv.unique_amount.toFixed(2)}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs">{inv.provider ?? inv.method}</td>
                    <td className="px-4 py-2.5"><Badge variant={STATUS_VARIANT[inv.status] ?? "gray"}>{inv.status}</Badge></td>
                    <td className="px-4 py-2.5 text-xs font-mono max-w-[120px] truncate" title={inv.tx_ref ?? ""}>{inv.tx_ref ? `${inv.tx_ref.slice(0, 12)}...` : "-"}</td>
                    <td className="px-4 py-2.5">
                      {inv.status === "pending" && (
                        <div className="flex gap-1.5">
                          <Button size="sm" onClick={() => action(inv.id, "approve")}>Approve</Button>
                          <Button size="sm" variant="danger" onClick={() => action(inv.id, "reject")}>Reject</Button>
                        </div>
                      )}
                      {inv.status === "approved" && (
                        <Button size="sm" variant="secondary" onClick={() => action(inv.id, "refund")}>Refund</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AdminCard>
      </div>
    </div>
  );
}