"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
 // import { EventBanner } from "@/components/calendar/EventBanner";
import type { DashboardOverview } from "@/lib/types";

const DashboardTour = dynamic(
  () =>
    import("@/components/onboarding/DashboardTour").then(
      (module) => module.DashboardTour
    ),
  { ssr: false }
);

interface RiskSnapshot {
  kill_switch_active: boolean;
  daily_loss_used_pct: number;
  open_positions: number;
  max_positions: number;
  trades_today: number;
  max_daily_trades: number;
  risk_score?: string;
}

interface ExchangeConnection {
  exchange: string;
  is_active: boolean;
}

function ActionItem({
  href,
  label,
  value,
  tone,
}: {
  href: string;
  label: string;
  value: string;
  tone: "green" | "yellow" | "red" | "gray";
}) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between gap-3 rounded-lg border border-border bg-bg-tertiary px-3 py-3 transition-colors hover:bg-bg-hover"
    >
      <span className="min-w-0">
        <span className="block text-xs text-text-muted">{label}</span>
        <span className="mt-0.5 block truncate text-sm font-medium">{value}</span>
      </span>
      <Badge variant={tone} dot>{tone === "green" ? "OK" : tone === "gray" ? "VIEW" : "CHECK"}</Badge>
    </Link>
  );
}

export default function OverviewPage() {
  const { token } = useAuth();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [risk, setRisk] = useState<RiskSnapshot | null>(null);
  const [unread, setUnread] = useState(0);
  const [connections, setConnections] = useState<ExchangeConnection[]>([]);

  useEffect(() => {
    if (!token) return;
    api<DashboardOverview>("/api/dashboard/overview", { token }).then(setOverview).catch(() => {});
    api<RiskSnapshot>("/api/risk/status", { token }).then(setRisk).catch(() => {});
    api<{ unread_count: number }>("/api/notifications?limit=1", { token })
      .then((body) => setUnread(body.unread_count))
      .catch(() => {});
    api<ExchangeConnection[]>("/api/exchanges", { token }).then(setConnections).catch(() => {});
  }, [token]);

  const o = overview;
  const activeConnections = connections.filter((c) => c.is_active).length;

  const riskTone: "green" | "yellow" | "red" | "gray" = !risk
    ? "gray"
    : risk.kill_switch_active || risk.daily_loss_used_pct >= 100
      ? "red"
      : risk.daily_loss_used_pct >= 80
        ? "yellow"
        : "green";
  const riskValue = !risk
    ? "Risk status unavailable"
    : risk.kill_switch_active
      ? "Kill switch active"
      : `Daily loss used ${risk.daily_loss_used_pct.toFixed(0)}%`;

  return (
    <div className="space-y-6">
      {/* <EventBanner /> */}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Portfolio Value" value={o ? `$${o.portfolio_value.toLocaleString()}` : "..."} />
        <StatCard
          label="Total P&L"
          value={o ? `${o.total_pnl >= 0 ? "+" : "-"}$${Math.abs(o.total_pnl).toLocaleString()}` : "..."}
        />
        <StatCard label="Open Positions" value={o ? o.open_trades.toString() : "..."} />
        <StatCard label="Active Signals" value={o ? o.active_signals.toString() : "..."} />
      </div>

      <Card>
        <CardHeader><CardTitle>Action Center</CardTitle></CardHeader>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <ActionItem href="/risk" label="Risk" value={riskValue} tone={riskTone} />
          <ActionItem
            href="/notifications"
            label="Notifications"
            value={unread > 0 ? `${unread} unread` : "All caught up"}
            tone={unread > 0 ? "yellow" : "green"}
          />
          <ActionItem
            href="/exchanges"
            label="Broker connections"
            value={activeConnections > 0 ? `${activeConnections} active` : "No active broker"}
            tone={activeConnections > 0 ? "green" : "red"}
          />
          <ActionItem
            href="/portfolio/positions"
            label="Open positions"
            value={o ? `${o.open_trades} open` : "..."}
            tone="gray"
          />
        </div>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Link
          href="/portfolio"
          className="rounded-lg border border-border bg-bg-secondary px-4 py-3 text-sm text-text-secondary transition-colors hover:border-green/40 hover:text-text-primary"
        >
          Review performance and equity curve →
        </Link>
        <Link
          href="/signals"
          className="rounded-lg border border-border bg-bg-secondary px-4 py-3 text-sm text-text-secondary transition-colors hover:border-green/40 hover:text-text-primary"
        >
          Browse the latest AI signals →
        </Link>
      </div>

      <DashboardTour />
    </div>
  );
}
