"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { BillingAdmin } from "@/components/admin/BillingAdmin";
import { AdminCard, AdminCardHeader, AdminCardTitle, AdminStatCard } from "@/components/admin/AdminCard";
import { clsx } from "clsx";

interface AdminUser {
  id: string; email: string; username: string; tier: string;
  is_admin: boolean; is_active: boolean; telegram_chat_id: string | null;
  created_at: string;
}
interface SystemStatus {
  scheduler: { enabled: boolean; interval_minutes: number; cooldown_hours: number };
  last_scan: { signals_generated?: number; by_market?: Record<string, number>; errors?: unknown[]; at?: string; resolved?: { tp?: number; sl?: number; expired?: number; skipped?: number; budget_exhausted?: boolean } };
  integrations: {
    trading_enabled: boolean; telegram_free_configured: boolean;
    telegram_premium_configured: boolean; telegram_vip_configured: boolean;
    smtp_configured: boolean;
  };
  supabase_reachable: boolean;
}
interface AuditEntry {
  id: string; admin_email: string; action: string; target_type: string;
  target_id: string | null; details: Record<string, unknown> | null; created_at: string;
}
interface AdminSignal {
  id: string; symbol: string; market: string; direction: string; confidence: number;
  status: string; tier_required: string; strategy: string | null;
  user_id: string | null; created_at: string;
}
interface SubRow {
  id: string; user_email?: string; tier: string; status: string;
  auto_renew: boolean; started_at: string; expires_at: string | null;
}
interface EngineStatus {
  stock?: { active: boolean };
  forex?: { active: boolean };
  crypto?: { active: boolean };
  crypto_alt?: { active: boolean };
  commodity?: { active: boolean };
}

const TABS = ["Overview", "Users", "Billing", "Signals", "System"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPage() {
  const { token, user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("Overview");
  const [notAuthorized, setNotAuthorized] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (!user.is_admin) {
      setNotAuthorized(true);
      router.replace("/");
    }
  }, [user, router]);

  if (notAuthorized || (user && !user.is_admin)) {
    return (
      <div className="p-8 text-center text-text-muted">Admin access required.</div>
    );
  }
  if (!user?.is_admin || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-green/30 border-t-green rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Distinct admin chrome — purple accent, banner header */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-bg-secondary via-bg-tertiary to-bg-secondary border border-purple/30">
        <div className="absolute inset-y-0 left-0 w-1 bg-purple" />
        <div className="flex items-center justify-between flex-wrap gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple/20 border border-purple/40 flex items-center justify-center text-purple">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-purple">Admin Console</h1>
                <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded bg-purple/20 text-purple border border-purple/30">
                  Restricted
                </span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">
                Signed in as <span className="text-text-secondary font-medium">{user.email}</span> — all actions are audited
              </p>
            </div>
          </div>
          <div className="flex gap-1.5 overflow-x-auto max-w-full pb-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={clsx(
                  "shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  tab === t
                    ? "bg-purple text-bg-primary"
                    : "bg-bg-tertiary text-text-secondary hover:text-text-primary hover:bg-bg-hover"
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {tab === "Overview" && <OverviewTab token={token} />}
      {tab === "Users" && <UsersTab token={token} />}
      {tab === "Billing" && <BillingAdmin token={token} />}
      {tab === "Signals" && <SignalsTab token={token} />}
      {tab === "System" && <SystemTab token={token} />}
    </div>
  );
}

// ---- Overview ------------------------------------------------------------

interface BillingStats {
  revenue_usd: number; pending_invoices: number; active_subscriptions: number; refunded_usd: number;
}

function OverviewTab({ token }: { token: string }) {
  const [billing, setBilling] = useState<BillingStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  useEffect(() => {
    Promise.all([
      api<BillingStats>("/api/billing/admin/stats", { token }).catch(() => null),
      api<AdminUser[]>("/api/admin/users?limit=5", { token }).catch(() => []),
      api<SystemStatus>("/api/admin/system", { token }).catch(() => null),
      api<AuditEntry[]>("/api/admin/audit?limit=8", { token }).catch(() => []),
    ]).then(([b, u, s, a]) => {
      setBilling(b); setUsers(u); setSystem(s); setAudit(a);
    });
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <AdminStatCard label="Revenue" value={billing ? `$${billing.revenue_usd.toLocaleString()}` : "-"} />
        <AdminStatCard label="Pending Invoices" value={billing ? `${billing.pending_invoices}` : "-"} />
        <AdminStatCard label="Active Subs" value={billing ? `${billing.active_subscriptions}` : "-"} />
        <AdminStatCard label="Scanning" value={system?.scheduler.enabled ? "ON" : "OFF"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Scheduler</AdminCardTitle></AdminCardHeader>
          <div className="space-y-2 text-sm">
            <Row k="Interval" v={system ? `${system.scheduler.interval_minutes} min` : "-"} />
            <Row k="Cooldown" v={system ? `${system.scheduler.cooldown_hours} h` : "-"} />
            <Row k="Last scan" v={system?.last_scan?.at ? new Date(system.last_scan.at).toLocaleString() : "never"} />
            <Row k="Signals (last)" v={system?.last_scan?.signals_generated != null ? `${system.last_scan.signals_generated}` : "-"} />
          </div>
        </AdminCard>

        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Integrations</AdminCardTitle></AdminCardHeader>
          <div className="space-y-2 text-sm">
            <Row k="Trading enabled" v={system?.integrations ? (system.integrations.trading_enabled ? "YES" : "no") : "-"} />
            <Row k="Telegram Free" v={system?.integrations ? (system.integrations.telegram_free_configured ? "OK" : "not set") : "-"} />
            <Row k="Telegram Premium" v={system?.integrations ? (system.integrations.telegram_premium_configured ? "OK" : "not set") : "-"} />
            <Row k="Telegram VIP" v={system?.integrations ? (system.integrations.telegram_vip_configured ? "OK" : "not set") : "-"} />
            <Row k="SMTP" v={system?.integrations ? (system.integrations.smtp_configured ? "OK" : "not set") : "-"} />
            <Row k="Supabase" v={system?.supabase_reachable != null ? (system.supabase_reachable ? "reachable" : "DOWN") : "-"} />
          </div>
        </AdminCard>

        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Recent Users</AdminCardTitle></AdminCardHeader>
          <div className="space-y-2 text-sm">
            {users.map((u) => (
              <div key={u.id} className="flex items-center justify-between border-b border-border/50 pb-2 last:border-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate font-medium">{u.email}</p>
                  <p className="text-xs text-text-muted">@{u.username}</p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Badge variant={u.tier === "vip" ? "blue" : u.tier === "premium" ? "yellow" : "gray"}>{u.tier}</Badge>
                  {u.is_admin && <Badge variant="green">admin</Badge>}
                </div>
              </div>
            ))}
            {users.length === 0 && <p className="text-xs text-text-muted">No users.</p>}
          </div>
        </AdminCard>
      </div>

      <AdminCard>
        <AdminCardHeader><AdminCardTitle>Recent Admin Activity</AdminCardTitle></AdminCardHeader>
        {audit.length === 0 ? (
          <p className="text-sm text-text-muted py-4 text-center">No admin actions recorded yet.</p>
        ) : (
          <div className="space-y-2 text-sm">
            {audit.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-2 last:border-0 last:pb-0">
                <div>
                  <span className="font-mono text-xs bg-bg-tertiary rounded px-2 py-0.5">{a.action}</span>
                  <span className="ml-2 text-text-secondary">{a.admin_email}</span>
                  <span className="ml-1 text-xs text-text-muted">{a.target_type}{a.target_id ? `:${a.target_id.slice(0, 8)}` : ""}</span>
                </div>
                <span className="text-xs text-text-muted">{new Date(a.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </AdminCard>
    </div>
  );
}

// ---- Users ---------------------------------------------------------------

function UsersTab({ token }: { token: string }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [danger, setDanger] = useState<{ user: AdminUser; mode: "deactivate" | "delete" } | null>(null);
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [anonymize, setAnonymize] = useState(false);
  const [dangerBusy, setDangerBusy] = useState(false);

  const load = useCallback(async (s = search, t = tier) => {
    try {
      const qs = new URLSearchParams({ limit: "100" });
      if (s) qs.set("search", s);
      if (t) qs.set("tier", t);
      setUsers(await api<AdminUser[]>(`/api/admin/users?${qs}`, { token }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load users");
    }
  }, [token, search, tier]);

  useEffect(() => { load(); }, [load]);

  async function update(u: AdminUser, patch: Partial<AdminUser>) {
    try {
      await api(`/api/admin/users/${u.id}`, { method: "PATCH", token, body: patch });
      setNotice(`Updated ${u.email}`); setError(null); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function resetPassword(u: AdminUser) {
    if (!confirm(`Reset password for ${u.email}? A temp password will be issued.`)) return;
    try {
      const r = await api<{ temporary_password: string }>(`/api/admin/users/${u.id}/reset-password`, {
        method: "POST", token, body: JSON.stringify({ notify: true }),
      });
      setNotice(`${u.email} reset - temporary password: ${r.temporary_password}`); setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  function openDanger(u: AdminUser, mode: "deactivate" | "delete") {
    setDanger({ user: u, mode });
    setReason("");
    setConfirmText("");
    setAnonymize(false);
  }

  async function runDanger() {
    if (!danger) return;
    const { user, mode } = danger;
    if (reason.trim().length < 2) { setError("A reason is required"); return; }
    if (mode === "delete" && confirmText.trim().toLowerCase() !== user.email.toLowerCase()) {
      setError("Type the user's email exactly to confirm deletion"); return;
    }
    setDangerBusy(true);
    setError(null);
    try {
      if (mode === "deactivate") {
        await api(`/api/admin/users/${user.id}/deactivate`, {
          method: "POST", token, body: JSON.stringify({ reason, anonymize }),
        });
        setNotice(`Deactivated ${user.email}`);
      } else {
        await api(`/api/admin/users/${user.id}`, {
          method: "DELETE", token, body: JSON.stringify({ reason, confirm: confirmText }),
        });
        setNotice(`Deleted ${user.email}`);
      }
      setDanger(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setDangerBusy(false);
    }
  }

  async function reactivate(u: AdminUser) {
    try {
      await api(`/api/admin/users/${u.id}/reactivate`, { method: "POST", token });
      setNotice(`Reactivated ${u.email}`); setError(null); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reactivate failed");
    }
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <Input label="Search (email / username)" value={search} onChange={(e) => { setSearch(e.target.value); load(e.target.value, tier); }} placeholder="user@example.com" />
        <Select
          label="Tier filter"
          value={tier}
          onChange={(e) => { setTier(e.target.value); load(search, e.target.value); }}
          options={[{ value: "", label: "All tiers" }, { value: "free", label: "Free" }, { value: "premium", label: "Premium" }, { value: "vip", label: "VIP" }]}
        />
        <Button variant="secondary" onClick={() => load()}>Refresh</Button>
      </div>

      <AdminCard padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-purple/25 text-left text-text-muted">
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Tier</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Telegram</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-text-muted">No users found.</td></tr>
              )}
              {users.map((u) => (
                <tr key={u.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5">
                    <p className="font-medium">{u.email}</p>
                    <p className="text-xs text-text-muted">@{u.username} · {new Date(u.created_at).toLocaleDateString()}</p>
                  </td>
                  <td className="px-4 py-2.5">
                    <Select
                      value={u.tier}
                      onChange={(e) => update(u, { tier: e.target.value })}
                      options={[{ value: "free", label: "Free" }, { value: "premium", label: "Premium" }, { value: "vip", label: "VIP" }]}
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Badge variant={u.is_admin ? "green" : "gray"}>{u.is_admin ? "admin" : "user"}</Badge>
                      <Button size="sm" variant="ghost" onClick={() => update(u, { is_admin: !u.is_admin })}>
                        {u.is_admin ? "Revoke" : "Grant"}
                      </Button>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant={u.is_active ? "green" : "red"}>{u.is_active ? "active" : "disabled"}</Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    {u.is_active ? (
                      <Button size="sm" variant={u.tier === "vip" ? "secondary" : "danger"} onClick={() => update(u, { is_active: false })}>
                        Disable
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => update(u, { is_active: true })}>Enable</Button>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <span className="text-xs text-text-muted">{u.telegram_chat_id ? "linked" : "—"}</span>
                      <Button size="sm" variant="secondary" onClick={() => resetPassword(u)}>Reset PW</Button>
                      {u.is_active ? (
                        <Button size="sm" variant="danger" onClick={() => openDanger(u, "deactivate")}>Deactivate</Button>
                      ) : (
                        <Button size="sm" variant="secondary" onClick={() => reactivate(u)}>Reactivate</Button>
                      )}
                      <Button size="sm" variant="danger" onClick={() => openDanger(u, "delete")}>Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <Modal
        open={!!danger}
        onClose={() => { if (!dangerBusy) setDanger(null); }}
        title={danger?.mode === "delete" ? "Permanently delete account" : "Deactivate account"}
      >
        {danger && (
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">
              {danger.mode === "delete"
                ? <>This permanently removes <span className="font-medium text-text-primary">{danger.user.email}</span> and all their data (signals, trades, connections). This cannot be undone.</>
                : <>This disables <span className="font-medium text-text-primary">{danger.user.email}</span>. They can be reactivated later.</>}
            </p>
            <Input
              label="Reason (kept in the audit log)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. fraudulent activity, user request"
            />
            {danger.mode === "deactivate" ? (
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input type="checkbox" checked={anonymize} onChange={(e) => setAnonymize(e.target.checked)} />
                Also anonymize PII (email/username), restorable on reactivate
              </label>
            ) : (
              <Input
                label={`Type "${danger.user.email}" to confirm`}
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={danger.user.email}
              />
            )}
            <div className="flex gap-2">
              <Button
                variant="danger"
                className="flex-1"
                onClick={runDanger}
                disabled={dangerBusy || reason.trim().length < 2 || (danger.mode === "delete" && confirmText.trim().toLowerCase() !== danger.user.email.toLowerCase())}
              >
                {dangerBusy ? "Working..." : danger.mode === "delete" ? "Permanently delete" : "Deactivate"}
              </Button>
              <Button variant="secondary" onClick={() => setDanger(null)} disabled={dangerBusy}>Cancel</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

// ---- Signals -------------------------------------------------------------

function SignalsTab({ token }: { token: string }) {
  const [signals, setSignals] = useState<AdminSignal[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSignals(await api<AdminSignal[]>("/api/admin/signals?limit=100", { token }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load signals");
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function invalidate(s: AdminSignal) {
    if (!confirm(`Invalidate ${s.symbol} (${s.direction})?`)) return;
    try {
      await api(`/api/admin/signals/${s.id}/invalidate`, { method: "POST", token });
      setError(null); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalidate failed");
    }
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red">{error}</p>}
      <AdminCard padding={false}>
        <div className="px-4 pt-4 flex items-center justify-between">
          <AdminCardTitle>All Signals (every tier)</AdminCardTitle>
          <Button size="sm" variant="secondary" onClick={load}>Refresh</Button>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-purple/25 text-left text-text-muted">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Market</th>
                <th className="px-4 py-2 font-medium">Direction</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Tier</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {signals.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-text-muted">No signals yet.</td></tr>
              )}
              {signals.map((s) => (
                <tr key={s.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5 font-medium">{s.symbol}</td>
                  <td className="px-4 py-2.5 capitalize">{s.market}</td>
                  <td className="px-4 py-2.5"><Badge variant={s.direction === "buy" ? "green" : "red"}>{s.direction}</Badge></td>
                  <td className="px-4 py-2.5 font-mono">{(s.confidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-2.5"><Badge variant={s.tier_required === "vip" ? "blue" : s.tier_required === "premium" ? "yellow" : "gray"}>{s.tier_required}</Badge></td>
                  <td className="px-4 py-2.5"><Badge variant={s.status === "active" ? "green" : s.status === "cancelled" ? "gray" : "yellow"}>{s.status}</Badge></td>
                  <td className="px-4 py-2.5 text-xs text-text-muted">{new Date(s.created_at).toLocaleString()}</td>
                  <td className="px-4 py-2.5">
                    {s.status !== "cancelled" && (
                      <Button size="sm" variant="danger" onClick={() => invalidate(s)}>Invalidate</Button>
                    )}
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

// ---- System --------------------------------------------------------------

function SystemTab({ token }: { token: string }) {
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [engine, setEngine] = useState<EngineStatus | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, e] = await Promise.all([
        api<SystemStatus>("/api/admin/system", { token }),
        api<EngineStatus>("/api/engine/status", { token }).catch(() => null),
      ]);
      setSystem(s); setEngine(e); setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load system status");
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function runScan() {
    try {
      const r = await api<{ signals_generated: number; errors: unknown[] }>("/api/engine/scan", { method: "POST", token });
      setNotice(`Scan complete - ${r.signals_generated} signals, ${r.errors.length} errors`); setError(null); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    }
  }

  async function resetDaily() {
    try {
      await api("/api/risk/reset-daily", { method: "POST", token });
      setNotice("Daily counters reset"); setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  async function resolveOutcomes() {
    try {
      const r = await api<{ tp: number; sl: number; expired: number; skipped: number; budget_exhausted?: boolean }>(
        "/api/admin/outcomes/resolve?budget_seconds=120&limit=2000",
        { method: "POST", token, timeoutMs: 150000 }
      );
      setNotice(
        `Outcomes: ${r.tp} TP / ${r.sl} SL, ${r.expired} expired, ${r.skipped} skipped` +
        (r.budget_exhausted ? " (budget hit - run again)" : "")
      );
      setError(null); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    }
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Scheduler</AdminCardTitle></AdminCardHeader>
          <div className="space-y-2 text-sm">
            <Row k="Enabled" v={system?.scheduler.enabled != null ? (system.scheduler.enabled ? "yes" : "no") : "-"} />
            <Row k="Interval" v={system ? `${system.scheduler.interval_minutes} min` : "-"} />
            <Row k="Cooldown" v={system ? `${system.scheduler.cooldown_hours} h` : "-"} />
            <Row k="Last scan" v={system?.last_scan?.at ? new Date(system.last_scan.at).toLocaleString() : "never"} />
            {system?.last_scan?.resolved && (
              <Row
                k="Resolved"
                v={`${system.last_scan.resolved.tp ?? 0} TP / ${system.last_scan.resolved.sl ?? 0} SL, ${system.last_scan.resolved.expired ?? 0} exp${system.last_scan.resolved.budget_exhausted ? " (partial)" : ""}`}
              />
            )}
            {system?.last_scan?.errors && system.last_scan.errors.length > 0 && (
              <p className="text-xs text-red mt-2">Last scan errors: {String(system.last_scan.errors).slice(0, 160)}</p>
            )}
          </div>
        </AdminCard>

        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Engines</AdminCardTitle></AdminCardHeader>
          <div className="space-y-2 text-sm">
            <Row k="Stocks" v={engine?.stock ? (engine.stock.active ? "market open" : "closed") : "-"} />
            <Row k="Forex" v={engine?.forex ? (engine.forex.active ? "market open" : "closed") : "-"} />
            <Row k="Crypto (Majors)" v={engine?.crypto ? (engine.crypto.active ? "active" : "idle") : "-"} />
            <Row k="Crypto (Meme/Hot)" v={engine?.crypto_alt ? (engine.crypto_alt.active ? "active" : "idle") : "-"} />
            <Row k="Commodities" v={engine?.commodity ? (engine.commodity.active ? "active" : "idle") : "-"} />
          </div>
        </AdminCard>

        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Actions</AdminCardTitle></AdminCardHeader>
          <div className="space-y-3">
            <Button className="w-full" onClick={runScan}>Run Engine Scan Now</Button>
            <Button className="w-full" variant="secondary" onClick={resolveOutcomes}>Resolve Signal Outcomes</Button>
            <Button className="w-full" variant="secondary" onClick={resetDaily}>Reset Daily Counters</Button>
            <Button className="w-full" variant="ghost" onClick={load}>Refresh</Button>
          </div>
        </AdminCard>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-text-muted">{k}</span>
      <span className="font-medium truncate">{v}</span>
    </div>
  );
}