"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { StatCard } from "@/components/ui/Card";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LineChart } from "@/components/charts/LineChart";
import type { DashboardOverview, PortfolioPerformance, Signal, Trade } from "@/lib/types";

export default function OverviewPage() {
  const { token } = useAuth();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [perf, setPerf] = useState<PortfolioPerformance | null>(null);

  useEffect(() => {
    if (!token) return;
    api<DashboardOverview>("/api/dashboard/overview", { token }).then(setOverview).catch(() => {});
    api<Signal[]>("/api/signals/?limit=5", { token }).then(setSignals).catch(() => {});
    api<Trade[]>("/api/portfolio/trades?limit=5", { token }).then(setTrades).catch(() => {});
    api<PortfolioPerformance>("/api/portfolio/performance", { token }).then(setPerf).catch(() => {});
  }, [token]);

  const o = overview;
  const pnlData = perf && perf.equity_curve.length > 0
    ? {
        labels: perf.equity_curve.map((p) => p.label),
        datasets: [{ label: "P&L", data: perf.equity_curve.map((p) => p.value), color: "#00D68F" }],
      }
    : null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Portfolio Value" value={o ? `$${o.portfolio_value.toLocaleString()}` : "..."} change={o ? `Win rate ${o.win_rate}%` : undefined} />
        <StatCard label="Total P&L" value={o ? `$${o.total_pnl.toLocaleString()}` : "..."} />
        <StatCard label="Win Rate" value={o ? `${o.win_rate}%` : "..."} />
        <StatCard label="Active Signals" value={o ? o.active_signals.toString() : "..."} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>P&L Curve</CardTitle></CardHeader>
          {pnlData
            ? <LineChart data={pnlData} height={250} />
            : <p className="text-sm text-text-muted py-8 text-center">No closed trades yet.</p>}
        </Card>

        <Card>
          <CardHeader><CardTitle>Recent Signals</CardTitle></CardHeader>
          <div className="space-y-3">
            {signals.length === 0 && <p className="text-sm text-text-muted">No signals yet</p>}
            {signals.map((s) => (
              <div key={s.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <div>
                  <p className="text-sm font-medium">{s.symbol}</p>
                  <p className="text-xs text-text-muted">{s.strategy || s.market}</p>
                </div>
                <Badge variant={s.direction === "buy" ? "green" : "red"}>{s.direction.toUpperCase()}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Open Trades</CardTitle></CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[540px]">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs text-text-muted py-2">Symbol</th>
                <th className="text-left text-xs text-text-muted py-2">Side</th>
                <th className="text-left text-xs text-text-muted py-2">Entry</th>
                <th className="text-left text-xs text-text-muted py-2">Strategy</th>
              </tr>
            </thead>
            <tbody>
              {trades.filter(t => t.status === "open").length === 0 && (
                <tr><td colSpan={4} className="py-6 text-center text-text-muted">No open trades</td></tr>
              )}
              {trades.filter(t => t.status === "open").map((t) => (
                <tr key={t.id} className="border-b border-border/50">
                  <td className="py-2.5 font-medium">{t.symbol}</td>
                  <td className="py-2.5"><Badge variant={t.side === "buy" ? "green" : "red"}>{t.side.toUpperCase()}</Badge></td>
                  <td className="py-2.5 font-mono">{t.entry_price.toLocaleString()}</td>
                  <td className="py-2.5 text-text-secondary">{t.strategy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
