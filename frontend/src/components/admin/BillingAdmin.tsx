"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface Invoice {
  id: string; tier: string; method: string; network: string | null;
  wallet_address: string | null; amount_usd: number; discount_usd: number;
  promo_code: string | null; status: string; tx_ref: string | null;
  created_at: string; expires_at: string; user_email?: string;
}
interface Promo { code: string; discount_pct: number; max_uses: number; uses_count: number; active: boolean }
interface Stats {
  revenue_usd: number; refunded_usd: number; net_usd: number;
  pending_invoices: number; approved_invoices: number;
  active_subscriptions: number;
  revenue_by_tier: Record<string, { count: number; revenue_usd: number }>;
}

const STATUS_VARIANT: Record<string, "green" | "red" | "yellow" | "gray" | "blue"> = {
  approved: "green", pending: "yellow", rejected: "red", refunded: "blue", cancelled: "gray",
};

export function BillingAdmin({ token }: { token: string }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [promos, setPromos] = useState<Promo[]>([]);
  const [newPromo, setNewPromo] = useState({ code: "", discount_pct: "20", max_uses: "100" });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [st, all, pr] = await Promise.all([
        api<Stats>("/api/billing/admin/stats", { token }),
        api<Invoice[]>("/api/billing/admin/invoices?limit=50", { token }),
        api<Promo[]>("/api/billing/admin/promos", { token }),
      ]);
      setStats(st); setInvoices(all); setPromos(pr); setError(null);
    } catch {
      setError("Could not load admin billing data");
    }
  }, [token]);

  useEffect(() => { refresh(); }, [refresh]);

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
        <StatCard label="Revenue" value={stats ? `$${stats.revenue_usd.toLocaleString()}` : "-"} />
        <StatCard label="Refunded" value={stats ? `$${stats.refunded_usd.toLocaleString()}` : "-"} />
        <StatCard label="Pending Invoices" value={stats ? `${stats.pending_invoices}` : "-"} />
        <StatCard label="Active Subs" value={stats ? `${stats.active_subscriptions}` : "-"} />
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle>Create Promo</CardTitle></CardHeader>
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
        </Card>

        <Card className="lg:col-span-2" padding={false}>
          <div className="px-4 pt-4"><CardTitle>All Invoices</CardTitle></div>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-muted">
                  <th className="px-4 py-2 font-medium">User</th>
                  <th className="px-4 py-2 font-medium">Tier</th>
                  <th className="px-4 py-2 font-medium">Amount</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Proof</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-6 text-center text-text-muted">No invoices.</td></tr>
                )}
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5 text-xs">{inv.user_email ?? "-"}</td>
                    <td className="px-4 py-2.5 capitalize">{inv.tier}</td>
                    <td className="px-4 py-2.5 font-mono">${inv.amount_usd.toLocaleString()}</td>
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
        </Card>
      </div>
    </div>
  );
}