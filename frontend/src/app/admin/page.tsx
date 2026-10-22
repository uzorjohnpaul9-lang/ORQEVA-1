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
import { AffiliateAdmin } from "@/components/admin/AffiliateAdmin";
import { AdminCard, AdminCardHeader, AdminCardTitle, AdminStatCard } from "@/components/admin/AdminCard";
import { clsx } from "clsx";
import type { AdminUserContext, BlockedIp, SecurityEvent, SupportTicket } from "@/lib/types";

interface AdminUser {
  id: string; email: string; username: string; tier: string;
  is_admin: boolean; is_active: boolean; telegram_chat_id: string | null;
  created_at: string; last_seen_at: string | null; is_online: boolean;
}
interface UsersPage {
  items: AdminUser[]; total: number; online: number; limit: number; offset: number;
  legacy: boolean;
}
interface UserStats {
  total: number; online: number; active: number; disabled: number;
  by_tier: { free: number; premium: number; vip: number };
  online_window_seconds: number;
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
interface ForwardTestBucket {
  market?: string; strategy?: string; markets?: string[];
  resolved: number; wins: number; losses: number; win_rate: number;
}
interface ForwardTestStats {
  overall: { resolved: number; wins: number; losses: number; win_rate: number; avg_r: number };
  by_market: ForwardTestBucket[];
  by_strategy: ForwardTestBucket[];
  excluded: { simulated: number; unknown: number };
  resolved_now?: { tp: number; sl: number; expired: number; skipped: number; budget_exhausted?: boolean };
}

const TABS = ["Overview", "Users", "Support", "Billing", "Affiliates", "Signals", "Security", "System"] as const;
type Tab = (typeof TABS)[number];

const USERS_PAGE_SIZE = 50;
const USERS_REFRESH_MS = 30_000;

/** Accept both the paginated response and the legacy bare list. */
function normalizeUsersPage(res: unknown): UsersPage {
  if (Array.isArray(res)) {
    const items = res as AdminUser[];
    return {
      items,
      total: items.length,
      online: items.filter((u) => u.is_online).length,
      limit: items.length,
      offset: 0,
      legacy: true,
    };
  }
  const page = res as Partial<UsersPage> | null;
  const items = page?.items ?? [];
  return {
    items,
    total: page?.total ?? items.length,
    online: page?.online ?? items.filter((u) => u.is_online).length,
    limit: page?.limit ?? USERS_PAGE_SIZE,
    offset: page?.offset ?? 0,
    legacy: false,
  };
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "just now";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function Presence({ online, lastSeen }: { online?: boolean; lastSeen?: string | null }) {
  if (online) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green">
        <span className="w-2 h-2 rounded-full bg-green" /> Online
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-muted">
      <span className="w-2 h-2 rounded-full bg-text-muted/40" /> Offline · {timeAgo(lastSeen)}
    </span>
  );
}

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
      {/* Distinct admin chrome â€” purple accent, banner header */}
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
                Signed in as <span className="text-text-secondary font-medium">{user.email}</span> â€” all actions are audited
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
      {tab === "Support" && <SupportTab token={token} />}
              {tab === "Billing" && <BillingAdmin token={token} />}
              {tab === "Affiliates" && <AffiliateAdmin token={token} />}
      {tab === "Signals" && <SignalsTab token={token} />}
      {tab === "Security" && <SecurityTab token={token} />}
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
  const [stats, setStats] = useState<UserStats | null>(null);

  useEffect(() => {
    Promise.all([
      api<BillingStats>("/api/billing/admin/stats", { token }).catch(() => null),
      api<unknown>("/api/admin/users?limit=5", { token }).catch(() => []),
      api<SystemStatus>("/api/admin/system", { token }).catch(() => null),
      api<AuditEntry[]>("/api/admin/audit?limit=8", { token }).catch(() => []),
      api<UserStats>("/api/admin/users/stats", { token }).catch(() => null),
    ]).then(([b, u, s, a, st]) => {
      setBilling(b); setUsers(normalizeUsersPage(u).items); setSystem(s); setAudit(a); setStats(st);
    });
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <AdminStatCard label="Total Users" value={stats ? `${stats.total}` : "-"} />
        <AdminStatCard label="Online Now" value={stats ? `${stats.online}` : "-"} change={stats ? "last 2 min" : undefined} />
        <AdminStatCard label="Active Accounts" value={stats ? `${stats.active}` : "-"} />
        <AdminStatCard label="Disabled" value={stats ? `${stats.disabled}` : "-"} />
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
                <div className="min-w-0 flex items-center gap-2">
                  <span
                    className={clsx("w-2 h-2 rounded-full shrink-0", u.is_online ? "bg-green" : "bg-text-muted/40")}
                    title={u.is_online ? "Online now" : `Last seen ${timeAgo(u.last_seen_at)}`}
                  />
                  <div className="min-w-0">
                    <p className="truncate font-medium">{u.email}</p>
                    <p className="text-xs text-text-muted">@{u.username}</p>
                  </div>
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
  const [total, setTotal] = useState(0);
  const [online, setOnline] = useState(0);
  const [legacy, setLegacy] = useState(false);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [danger, setDanger] = useState<{ user: AdminUser; mode: "deactivate" | "delete" } | null>(null);
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [anonymize, setAnonymize] = useState(false);
  const [dangerBusy, setDangerBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams({
        limit: String(USERS_PAGE_SIZE),
        offset: String(page * USERS_PAGE_SIZE),
      });
      if (search.trim()) qs.set("search", search.trim());
      if (tier) qs.set("tier", tier);
      const [listRes, statsRes] = await Promise.all([
        api<unknown>(`/api/admin/users?${qs}`, { token }),
        api<UserStats>("/api/admin/users/stats", { token }).catch(() => null),
      ]);
      const normalized = normalizeUsersPage(listRes);
      setUsers(normalized.items);
      setTotal(normalized.total);
      setOnline(normalized.online);
      setLegacy(normalized.legacy);
      setStats(statsRes);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load users");
    }
  }, [token, search, tier, page]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  useEffect(() => {
    const iv = setInterval(load, USERS_REFRESH_MS);
    return () => clearInterval(iv);
  }, [load]);

  const totalUsers = stats?.total ?? (legacy ? null : total);
  const onlineUsers = stats?.online ?? (legacy ? null : online);
  const activeUsers = stats?.active ?? (legacy ? null : users.filter((u) => u.is_active).length);
  const lastShown = total > 0 ? Math.min(total, (page + 1) * USERS_PAGE_SIZE) : 0;
  const hasNext = legacy ? users.length >= USERS_PAGE_SIZE : lastShown < total;
  const fmtCount = (n: number | null) => (n == null ? "-" : `${n}`);

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

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <AdminStatCard label="Total Users" value={fmtCount(totalUsers)} />
        <AdminStatCard label="Online Now" value={fmtCount(onlineUsers)} change="last 2 min" />
        <AdminStatCard label="Active Accounts" value={fmtCount(activeUsers)} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <Input label="Search (email / username)" value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="user@example.com" />
        <Select
          label="Tier filter"
          value={tier}
          onChange={(e) => { setTier(e.target.value); setPage(0); }}
          options={[{ value: "", label: "All tiers" }, { value: "free", label: "Free" }, { value: "premium", label: "Premium" }, { value: "vip", label: "VIP" }]}
        />
        <Button variant="secondary" onClick={() => load()}>Refresh</Button>
      </div>

      <AdminCard padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[860px]">
            <thead>
              <tr className="border-b border-purple/25 text-left text-text-muted">
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Tier</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Account</th>
                <th className="px-4 py-2 font-medium">Online</th>
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
                    <p className="text-xs text-text-muted">
                      @{u.username} · {new Date(u.created_at).toLocaleDateString()}
                      {u.telegram_chat_id && <span className="ml-1.5 text-purple">· TG</span>}
                    </p>
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
                    <Badge variant={u.is_active ? "green" : "red"}>{u.is_active ? "Active" : "Disabled"}</Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    <Presence online={u.is_online} lastSeen={u.last_seen_at} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <Button size="sm" variant="secondary" onClick={() => resetPassword(u)}>Reset PW</Button>
                      {u.is_active ? (
                        <Button size="sm" variant={u.tier === "vip" ? "secondary" : "danger"} onClick={() => update(u, { is_active: false })}>
                          Disable
                        </Button>
                      ) : (
                        <Button size="sm" onClick={() => update(u, { is_active: true })}>Enable</Button>
                      )}
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
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-t border-border/50 text-xs text-text-muted">
          <span>
            {legacy
              ? `${users.length} shown`
              : total === 0
                ? "0 users"
                : `${page * USERS_PAGE_SIZE + 1}–${lastShown} of ${total} users`}
            {" · "}
            <span className="text-green">{fmtCount(onlineUsers)} online</span>
          </span>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
              Prev
            </Button>
            <span>
              {legacy ? `Page ${page + 1}` : `Page ${page + 1} of ${Math.max(1, Math.ceil(total / USERS_PAGE_SIZE))}`}
            </span>
            <Button size="sm" variant="secondary" disabled={!hasNext} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
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



function SupportTab({ token }: { token: string }) {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [stats, setStats] = useState<{open:number;in_progress:number;total:number}|null>(null);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState("in_progress");
  const [priority, setPriority] = useState("normal");
  const [notice, setNotice] = useState<string|null>(null);
  const [error, setError] = useState<string|null>(null);
  const [busy, setBusy] = useState(false);
  const [ctx, setCtx] = useState<AdminUserContext|null>(null);

  const load = useCallback(async () => {
    try {
      const [t,s] = await Promise.all([
        api<SupportTicket[]>("/api/admin/support", {token}),
        api<{open:number;in_progress:number;total:number}>("/api/admin/support/stats",{token}).catch(()=>null),
      ]);
      setTickets(t); setStats(s); setError(null);
    } catch (e){ setError(e instanceof Error?e.message:"load failed"); }
  },[token]);
  useEffect(()=>{load()},[load]);

  const open = async (tick: SupportTicket) => {
    setSelected(tick); setReply(tick.reply||""); setStatus(tick.status||"in_progress"); setPriority(tick.priority||"normal"); setCtx(null); setError(null); setNotice(null);
    if (tick.user_id) {
      try { setCtx(await api<AdminUserContext>(`/api/admin/users/${tick.user_id}/context`,{token})); } catch {}
    }
  };

  const sendReply = async () => {
    if (!selected || !reply.trim()) return;
    setBusy(true); setError(null);
    try {
      await api(`/api/admin/support/${selected.id}/reply`, {method:"POST",token,body:{message:reply,status,priority}});
      setNotice("Replied & updated"); await load(); open(selected);
    } catch (e){ setError(e instanceof Error?e.message:"reply failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      {error&&<p className="text-sm text-red">{error}</p>}{notice&&<p className="text-sm text-green">{notice}</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AdminCard padding={false}>
          <div className="px-4 pt-4 flex items-center justify-between">
            <AdminCardTitle>Support Queue {stats?`(open ${stats.open} / in-prog ${stats.in_progress})`: ""}</AdminCardTitle>
            <Button size="sm" variant="secondary" onClick={load}>Refresh</Button>
          </div>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm min-w-[700px]">
              <thead><tr className="border-b border-purple/25 text-left text-text-muted"><th className="px-4 py-2">Subject</th><th className="px-4 py-2">Email</th><th className="px-4 py-2">Category</th><th className="px-4 py-2">Status</th><th className="px-4 py-2">Priority</th><th className="px-4 py-2">Created</th><th className="px-4 py-2">Actions</th></tr></thead>
              <tbody>
                {tickets.length===0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-text-muted">No tickets.</td></tr>}
                {tickets.map(t=>(
                  <tr key={t.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5">{t.subject}</td>
                    <td className="px-4 py-2.5 text-xs text-text-muted">{t.user_email||t.email}</td>
                    <td className="px-4 py-2.5 capitalize">{t.category}</td>
                    <td className="px-4 py-2.5"><Badge variant={t.status==="open"?"yellow":t.status==="in_progress"?"blue":t.status==="resolved"?"green":"gray"}>{t.status}</Badge></td>
                    <td className="px-4 py-2.5"><Badge variant={t.priority==="high"?"red":t.priority==="low"?"gray":"blue"}>{t.priority||"normal"}</Badge></td>
                    <td className="px-4 py-2.5 text-xs text-text-muted">{new Date(t.created_at).toLocaleString()}</td>
                    <td className="px-4 py-2.5"><Button size="sm" variant="secondary" onClick={()=>open(t)}>View</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AdminCard>

        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Ticket</AdminCardTitle></AdminCardHeader>
          {!selected ? <p className="text-sm text-text-muted">Select a ticket.</p> : (
            <div className="space-y-3 text-sm">
              <div><p className="text-text-muted">From</p><p>{selected.user_email||selected.email} {selected.user_id?`(user:${selected.user_id.slice(0,8)})`: "anon"}</p></div>
              <div><p className="text-text-muted">Subject</p><p className="font-medium">{selected.subject}</p></div>
              <div><p className="text-text-muted">Message</p><pre className="whitespace-pre-wrap bg-bg-tertiary rounded p-2 text-xs">{selected.message}</pre></div>
              <div className="grid grid-cols-2 gap-2">
                <Select label="Status" value={status} onChange={e=>setStatus(e.target.value)} options={[{value:"open",label:"open"},{value:"in_progress",label:"in_progress"},{value:"resolved",label:"resolved"},{value:"closed",label:"closed"}]} />
                <Select label="Priority" value={priority} onChange={e=>setPriority(e.target.value)} options={[{value:"low",label:"low"},{value:"normal",label:"normal"},{value:"high",label:"high"}]} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-text-secondary">Reply</label>
                <textarea className="w-full bg-bg-tertiary border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary min-h-[120px]" value={reply} onChange={e=>setReply(e.target.value)} />
              </div>
              <Button disabled={busy} onClick={sendReply}>{busy?"Sending...":"Send Reply"}</Button>
              {selected.reply && <div><p className="text-text-muted">Last reply</p><pre className="whitespace-pre-wrap bg-bg-tertiary rounded p-2 text-xs">{selected.reply}</pre>{selected.replied_at&&<p className="text-xs text-text-muted mt-1">{new Date(selected.replied_at).toLocaleString()}</p>}</div>}
            </div>
          )}
        </AdminCard>
      </div>

      {ctx && (
        <AdminCard>
          <AdminCardHeader><AdminCardTitle>Read-only Context</AdminCardTitle></AdminCardHeader>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-text-muted mb-1">Profile</p>
              <Row k="Email" v={ctx.profile.email} /><Row k="Tier" v={ctx.profile.tier} /><Row k="Admin" v={ctx.profile.is_admin?"yes":"no"} />
              <Row k="Account" v={ctx.profile.is_active?"Active":"Disabled"} />
              <Row k="Online" v={ctx.profile.is_online ? "yes" : "no"} />
              <Row k="Last seen" v={ctx.profile.last_seen_at ? new Date(ctx.profile.last_seen_at).toLocaleString() : "never"} />
            </div>
            <div>
              <p className="text-text-muted mb-1">Activity</p>
              <Row k="Open" v={String(ctx.activity.open_positions)} /><Row k="Closed" v={String(ctx.activity.closed_positions)} /><Row k="Realized PnL" v={ctx.activity.realized_pnl.toFixed(2)} /><Row k="Unread" v={String(ctx.notifications_unread)} />
            </div>
            <div>
              <p className="text-text-muted mb-1">Tickets</p>
              {ctx.support_tickets.length===0? <p className="text-xs text-text-muted">None</p>: ctx.support_tickets.map((t: Record<string, unknown>, i: number)=><p key={i} className="text-xs truncate">{String(t.status)}:{String(t.subject)}</p>)}
            </div>
          </div>
        </AdminCard>
      )}
    </div>
  );
}

// ---- Security (Phase G) ---------------------------------------------------
function SecurityTab({ token }: { token: string }) {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [blocks, setBlocks] = useState<BlockedIp[]>([]);
  const [kind, setKind] = useState("");
  const [severity, setSeverity] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const q = new URLSearchParams({ limit: "150" });
      if (kind) q.set("kind", kind);
      if (severity) q.set("severity", severity);
      const [ev, bl] = await Promise.all([
        api<SecurityEvent[]>(`/api/admin/sentinel?${q.toString()}`, { token }),
        api<BlockedIp[]>("/api/admin/sentinel/blocks", { token }).catch(() => []),
      ]);
      setEvents(ev); setBlocks(bl); setError(null);
    } catch (e) { setError(e instanceof Error ? e.message : "load failed"); }
  }, [token, kind, severity]);
  useEffect(() => { load(); }, [load]);

  const resolve = async (id: string) => {
    setBusy(true); setError(null);
    try {
      await api(`/api/admin/sentinel/${id}/resolve`, { method: "POST", token });
      setNotice("Event resolved"); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "resolve failed"); }
    finally { setBusy(false); }
  };

  const unblock = async (ip: string) => {
    setBusy(true); setError(null);
    try {
      await api(`/api/admin/sentinel/blocks/${encodeURIComponent(ip)}/unblock`, { method: "POST", token });
      setNotice(`Unblocked ${ip}`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "unblock failed"); }
    finally { setBusy(false); }
  };

  const sevBadge = (s: string) =>
    s === "critical" ? "red" : s === "high" ? "yellow" : s === "warn" ? "blue" : "gray";

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      <div className="flex flex-wrap items-end gap-3">
        <Select label="Kind" value={kind} onChange={(e) => { setKind(e.target.value); setNotice(null); }}
          options={[{ value: "", label: "all" }, { value: "login_fail", label: "login_fail" }, { value: "rate_limit", label: "rate_limit" }, { value: "abuse", label: "abuse" }, { value: "suspicious", label: "suspicious" }, { value: "geo", label: "geo" }, { value: "anomaly", label: "anomaly" }]} />
        <Select label="Severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setNotice(null); }}
          options={[{ value: "", label: "all" }, { value: "info", label: "info" }, { value: "warn", label: "warn" }, { value: "high", label: "high" }, { value: "critical", label: "critical" }]} />
        <Button size="sm" variant="secondary" onClick={load}>Refresh</Button>
        <p className="text-xs text-text-muted ml-auto max-w-md">
          Sentinel complements Cloudflare WAF and Supabase RLS; blocks auto-expire (TTL) and are re-checked each scan.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <AdminCard padding={false} className="lg:col-span-2">
          <div className="px-4 pt-4"><AdminCardTitle>Security Events</AdminCardTitle></div>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm min-w-[760px]">
              <thead><tr className="border-b border-purple/25 text-left text-text-muted">
                <th className="px-4 py-2">Severity</th><th className="px-4 py-2">Kind</th><th className="px-4 py-2">IP</th><th className="px-4 py-2">Details</th><th className="px-4 py-2">When</th><th className="px-4 py-2">Actions</th>
              </tr></thead>
              <tbody>
                {events.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-text-muted">No events.</td></tr>}
                {events.map((e) => (
                  <tr key={e.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5"><Badge variant={sevBadge(e.severity) as "red" | "yellow" | "blue" | "gray"}>{e.severity}</Badge></td>
                    <td className="px-4 py-2.5">{e.kind}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{e.ip || "-"}</td>
                    <td className="px-4 py-2.5 text-xs text-text-muted max-w-[260px] truncate" title={JSON.stringify(e.details || {})}>{JSON.stringify(e.details || {})}</td>
                    <td className="px-4 py-2.5 text-xs text-text-muted">{new Date(e.created_at).toLocaleString()}</td>
                    <td className="px-4 py-2.5">
                      {e.resolved
                        ? <Badge variant="green">resolved</Badge>
                        : <Button size="sm" variant="secondary" disabled={busy} onClick={() => resolve(e.id)}>Resolve</Button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AdminCard>

        <AdminCard padding={false}>
          <div className="px-4 pt-4"><AdminCardTitle>Auto-blocked IPs</AdminCardTitle></div>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm min-w-[280px]">
              <thead><tr className="border-b border-purple/25 text-left text-text-muted">
                <th className="px-4 py-2">IP</th><th className="px-4 py-2">Reason</th><th className="px-4 py-2">Until</th><th className="px-4 py-2" />
              </tr></thead>
              <tbody>
                {blocks.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-text-muted">No active blocks.</td></tr>}
                {blocks.map((b) => (
                  <tr key={b.ip} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5 font-mono text-xs">{b.ip}</td>
                    <td className="px-4 py-2.5 text-xs text-text-muted max-w-[140px] truncate" title={b.reason}>{b.reason || "-"}</td>
                    <td className="px-4 py-2.5 text-xs text-text-muted">{b.blocked_until ? new Date(b.blocked_until).toLocaleTimeString() : "-"}</td>
                    <td className="px-4 py-2.5"><Button size="sm" variant="secondary" disabled={busy} onClick={() => unblock(b.ip)}>Unblock</Button></td>
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

function SystemTab({ token }: { token: string }) {
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [engine, setEngine] = useState<EngineStatus | null>(null);
  const [forwardTest, setForwardTest] = useState<ForwardTestStats | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadForwardTest = useCallback(async () => {
    try {
      setForwardTest(await api<ForwardTestStats>("/api/admin/forward-test", { method: "POST", token }));
    } catch {
      /* forward-test is non-critical; leave the last value in place */
    }
  }, [token]);

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
    await loadForwardTest();
  }, [token, loadForwardTest]);

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

  async function runForwardTest() {
    try {
      const r = await api<ForwardTestStats>(
        "/api/admin/forward-test?resolve=true&budget_seconds=120&limit=2000",
        { method: "POST", token, timeoutMs: 150000 }
      );
      setForwardTest(r);
      if (r.resolved_now) {
        const rn = r.resolved_now;
        setNotice(
          `Forward test: ${rn.tp} TP / ${rn.sl} SL, ${rn.expired} expired, ${rn.skipped} skipped` +
          (rn.budget_exhausted ? " (budget hit - run again)" : "")
        );
      } else {
        setNotice("Forward test refreshed");
      }
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Forward test failed");
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
            <Button className="w-full" variant="secondary" onClick={runForwardTest}>Run Live-Only Forward Test</Button>
            <Button className="w-full" variant="secondary" onClick={resolveOutcomes}>Resolve Signal Outcomes</Button>
            <Button className="w-full" variant="secondary" onClick={resetDaily}>Reset Daily Counters</Button>
            <Button className="w-full" variant="ghost" onClick={load}>Refresh</Button>
          </div>
        </AdminCard>
      </div>

      <AdminCard>
        <AdminCardHeader>
          <AdminCardTitle>Live-Only Forward Test (excludes simulated)</AdminCardTitle>
        </AdminCardHeader>
        <div className="space-y-6 text-sm">
          {forwardTest === null && <p className="text-text-muted">Loading forward-test...</p>}
          {forwardTest && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <AdminStatCard label="Live Resolved" value={forwardTest.overall.resolved.toLocaleString()} />
                <AdminStatCard label="Win Rate" value={`${forwardTest.overall.win_rate.toFixed(1)}%`} />
                <AdminStatCard label="Wins / Losses" value={`${forwardTest.overall.wins} / ${forwardTest.overall.losses}`} />
                <AdminStatCard label="Avg R (live)" value={forwardTest.overall.avg_r.toFixed(3)} />
              </div>
              {forwardTest.excluded.simulated > 0 || forwardTest.excluded.unknown > 0 && (
                <p className="text-xs text-text-muted">
                  Excluded: {forwardTest.excluded.simulated} simulated, {forwardTest.excluded.unknown} unknown data-source.
                </p>
              )}
              {forwardTest.by_market.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">Per Market (live-only)</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[480px]">
                      <thead>
                        <tr className="text-left text-text-muted border-b border-border/50">
                          <th className="py-1.5 pr-3">Market</th>
                          <th className="py-1.5 pr-3">Resolved</th>
                          <th className="py-1.5 pr-3">Wins/Losses</th>
                          <th className="py-1.5">Win %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {forwardTest.by_market.map((m) => (
                          <tr key={m.market} className="border-b border-border/50 last:border-0">
                            <td className="py-1.5 pr-3 capitalize">{m.market}</td>
                            <td className="py-1.5 pr-3">{m.resolved}</td>
                            <td className="py-1.5 pr-3">{m.wins} / {m.losses}</td>
                            <td className="py-1.5">{m.win_rate.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {forwardTest.by_strategy.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">Per Strategy (live-only)</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px]">
                      <thead>
                        <tr className="text-left text-text-muted border-b border-border/50">
                          <th className="py-1.5 pr-3">Strategy</th>
                          <th className="py-1.5 pr-3">Markets</th>
                          <th className="py-1.5 pr-3">Resolved</th>
                          <th className="py-1.5 pr-3">Wins/Losses</th>
                          <th className="py-1.5">Win %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {forwardTest.by_strategy.map((s) => (
                          <tr key={s.strategy} className="border-b border-border/50 last:border-0">
                            <td className="py-1.5 pr-3">{s.strategy}</td>
                            <td className="py-1.5 pr-3 text-text-muted truncate">{(s.markets || []).join(", ")}</td>
                            <td className="py-1.5 pr-3">{s.resolved}</td>
                            <td className="py-1.5 pr-3">{s.wins} / {s.losses}</td>
                            <td className="py-1.5">{s.win_rate.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </AdminCard>
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
// ---- Support --------------------------------------------------------------


