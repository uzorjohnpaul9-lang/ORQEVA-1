"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { AdminCard, AdminCardHeader, AdminCardTitle, AdminStatCard } from "@/components/admin/AdminCard";

interface Partner {
  id: string;
  name: string;
  url: string;
  category: string;
  active: boolean;
  click_count: number;
  conversion_count: number;
  revenue_usd: number;
  conversion_rate: number;
}

interface Summary {
  partners: number;
  clicks: number;
  conversions: number;
  revenue_usd: number;
  conversion_rate: number;
}

const CATEGORY_LABELS: Record<string, string> = {
  broker: "Broker",
  prop_firm: "Prop Firm",
  partner: "Partner",
};

const CATEGORY_OPTIONS = [
  { value: "broker", label: "Broker" },
  { value: "prop_firm", label: "Prop Firm" },
  { value: "partner", label: "Partner" },
];

export function AffiliateAdmin({ token }: { token: string }) {
  const [partners, setPartners] = useState<Partner[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [form, setForm] = useState({ name: "", url: "", category: "broker" });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const r = await api<{ partners: Partner[]; summary: Summary }>("/api/admin/affiliates", { token });
      setPartners(r.partners);
      setSummary(r.summary);
      setError(null);
    } catch {
      setError("Could not load affiliate data");
    }
  }, [token]);

  useEffect(() => { refresh(); }, [refresh]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setNotice(null); setError(null);
    try {
      await api("/api/admin/affiliates", {
        method: "POST", token,
        body: JSON.stringify({
          name: form.name.trim(),
          url: form.url.trim(),
          category: form.category,
        }),
      });
      setForm({ name: "", url: "", category: "broker" });
      setNotice("Partner added");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add partner");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(p: Partner) {
    setBusy(true);
    try {
      await api(`/api/admin/affiliates/${p.id}/toggle`, {
        method: "POST", token,
        body: JSON.stringify({ active: !p.active }),
      });
      await refresh();
    } catch {
      setError("Could not update partner");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <AdminStatCard label="Partners" value={String(summary.partners)} />
          <AdminStatCard label="Clicks" value={summary.clicks.toLocaleString()} />
          <AdminStatCard label="Conversions" value={String(summary.conversions)} />
          <AdminStatCard label="Revenue" value={`$${summary.revenue_usd.toLocaleString()}`} change={`${summary.conversion_rate}% rate`} />
        </div>
      )}

      {error && <AdminCard><p className="text-sm text-red">{error}</p></AdminCard>}
      {notice && <AdminCard><p className="text-sm text-green">{notice}</p></AdminCard>}

      <AdminCard>
        <AdminCardHeader><AdminCardTitle>Add Partner</AdminCardTitle></AdminCardHeader>
        <form onSubmit={create} className="space-y-4">
          <Input
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="BrokerCo"
            required
          />
          <Input
            label="Referral URL"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            placeholder="https://broker.example/ref?id=123"
            required
          />
          <Select
            label="Category"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            options={CATEGORY_OPTIONS}
          />
          <Button type="submit" disabled={busy}>{busy ? "Working..." : "Add Partner"}</Button>
        </form>
      </AdminCard>

      <AdminCard padding={false}>
        <div className="p-5 pb-0"><AdminCardTitle>Partners</AdminCardTitle></div>
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs text-text-muted px-5 py-2 font-medium">Partner</th>
                <th className="text-left text-xs text-text-muted px-5 py-2 font-medium">Category</th>
                <th className="text-right text-xs text-text-muted px-5 py-2 font-medium">Clicks</th>
                <th className="text-right text-xs text-text-muted px-5 py-2 font-medium">Conv.</th>
                <th className="text-right text-xs text-text-muted px-5 py-2 font-medium">Revenue</th>
                <th className="text-center text-xs text-text-muted px-5 py-2 font-medium">Status</th>
                <th className="px-5 py-2" />
              </tr>
            </thead>
            <tbody>
              {partners.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-6 text-center text-text-muted">No partners yet.</td></tr>
              )}
              {partners.map((p) => (
                <tr key={p.id} className="border-b border-border/50 last:border-0">
                  <td className="px-5 py-2.5">
                    <span className="font-medium">{p.name}</span>
                    <p className="text-xs text-text-muted break-all max-w-[240px]">{p.url}</p>
                  </td>
                  <td className="px-5 py-2.5">{CATEGORY_LABELS[p.category] ?? p.category}</td>
                  <td className="px-5 py-2.5 text-right font-mono">{p.click_count}</td>
                  <td className="px-5 py-2.5 text-right font-mono">{p.conversion_count}</td>
                  <td className="px-5 py-2.5 text-right font-mono">${p.revenue_usd}</td>
                  <td className="px-5 py-2.5 text-center">
                    <Badge variant={p.active ? "green" : "gray"}>{p.active ? "Active" : "Off"}</Badge>
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    <Button variant={p.active ? "danger" : "secondary"} size="sm" onClick={() => toggle(p)} disabled={busy}>
                      {p.active ? "Disable" : "Enable"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AdminCard>
    </div>
  );
}
