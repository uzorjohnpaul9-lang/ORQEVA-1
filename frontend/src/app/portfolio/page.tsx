"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/tables/DataTable";
import { LineChart } from "@/components/charts/LineChart";
import { DonutChart } from "@/components/charts/DonutChart";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PortfolioPerformance, Trade } from "@/lib/types";

const DONUT_COLORS = ["#3B82F6", "#00D68F", "#FFBE0B", "#FF4757", "#A855F7"];

export default function PortfolioPage() {
  const { token } = useAuth();
  const [perf, setPerf] = useState<PortfolioPerformance | null>(null);
  const [closed, setClosed] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    (async () => {
      try {
        const [p, t] = await Promise.all([
          api<PortfolioPerformance>("/api/portfolio/performance", { token }),
          api<Trade[]>("/api/portfolio/trades?status=closed&limit=50", { token }),
        ]);
        if (active) { setPerf(p); setClosed(t); }
      } catch {
        if (active) setError("Could not load portfolio");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Portfolio</h1>
        <p className="text-sm text-text-secondary mt-1">Holdings and realized performance</p>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {!loading && !error && perf && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Portfolio Value"
              value={`$${perf.portfolio_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
            />
            <StatCard label="Win Rate" value={`${perf.win_rate}%`} change={`${perf.wins}W / ${perf.losses}L`} />
            <StatCard label="Closed Trades" value={(perf.wins + perf.losses).toString()} />
            <StatCard
              label="Total P&L"
              value={`${perf.total_pnl >= 0 ? "+" : "-"}$${Math.abs(perf.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
              change={perf.max_drawdown < 0 ? `max DD -$${Math.abs(perf.max_drawdown).toLocaleString()}` : undefined}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Equity Curve</CardTitle>
              </CardHeader>
              {perf.equity_curve.length > 0 ? (
                <LineChart
                  data={{
                    labels: perf.equity_curve.map((p) => p.label),
                    datasets: [{ label: "Equity", data: perf.equity_curve.map((p) => p.value), color: "#00D68F" }],
                  }}
                />
              ) : (
                <p className="text-sm text-text-muted py-8 text-center">No closed trades yet.</p>
              )}
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Allocation by Market</CardTitle>
              </CardHeader>
              {perf.allocation.length > 0 ? (
                <DonutChart
                  labels={perf.allocation.map((a) => a.market)}
                  data={perf.allocation.map((a) => a.value)}
                  colors={DONUT_COLORS}
                />
              ) : (
                <p className="text-sm text-text-muted py-8 text-center">No allocation data.</p>
              )}
            </Card>
          </div>

          <Card padding={false}>
            <div className="px-4 pt-4">
              <CardTitle>Trade History</CardTitle>
            </div>
            <div className="mt-3">
              <DataTable<Trade>
                data={closed}
                columns={[
                  {
                    key: "symbol",
                    header: "Symbol",
                    render: (t) => (
                      <span className="flex items-center gap-2">
                        <span className="font-medium">{t.symbol}</span>
                        <Badge variant={t.side === "buy" ? "green" : "red"}>{t.side.toUpperCase()}</Badge>
                      </span>
                    ),
                  },
                  { key: "market", header: "Market", render: (t) => <span className="capitalize">{t.market}</span> },
                  { key: "entry", header: "Entry", render: (t) => <span className="font-mono">{t.entry_price.toLocaleString()}</span> },
                  { key: "exit", header: "Exit", render: (t) => <span className="font-mono">{t.exit_price != null ? t.exit_price.toLocaleString() : "-"}</span> },
                  {
                    key: "pnl",
                    header: "P&L",
                    render: (t) => (
                      <span className={clsx("font-mono font-bold", (t.pnl ?? 0) >= 0 ? "text-green" : "text-red")}>
                        {(t.pnl ?? 0) >= 0 ? "+" : ""}{(t.pnl ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    ),
                  },
                  { key: "strategy", header: "Strategy", render: (t) => <span className="text-text-muted">{t.strategy}</span> },
                ]}
              />
            </div>
          </Card>
        </>
      )}
      {loading && <p className={clsx("text-sm text-text-muted")}>Loading portfolio...</p>}
    </div>
  );
}
