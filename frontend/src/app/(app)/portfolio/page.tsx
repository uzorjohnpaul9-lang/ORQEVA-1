"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { LineChart } from "@/components/charts/LineChart";
import { DonutChart } from "@/components/charts/DonutChart";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PortfolioPerformance } from "@/lib/types";

const DONUT_COLORS = ["#3B82F6", "#00D68F", "#FFBE0B", "#FF4757", "#A855F7"];

export default function PortfolioPerformancePage() {
  const { token } = useAuth();
  const [perf, setPerf] = useState<PortfolioPerformance | null>(null);
  const [ledger, setLedger] = useState<"" | "demo" | "live">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    const demoSuffix = ledger ? `is_demo=${ledger === "demo"}` : "";
    const perfUrl = demoSuffix ? `/api/portfolio/performance?${demoSuffix}` : "/api/portfolio/performance";
    setLoading(true);
    api<PortfolioPerformance>(perfUrl, { token })
      .then((data) => {
        if (active) {
          setPerf(data);
          setError(null);
        }
      })
      .catch(() => {
        if (active) setError("Could not load portfolio");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [token, ledger]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Performance</h1>
          <p className="text-sm text-text-secondary mt-1">Realized performance and allocation</p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-bg-tertiary p-1">
          {([["", "All"], ["demo", "Demo"], ["live", "Live"]] as const).map(([val, label]) => (
            <button
              key={val}
              type="button"
              onClick={() => setLedger(val)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                ledger === val ? "bg-green text-bg" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {loading && <p className="text-sm text-text-muted">Loading portfolio...</p>}
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
        </>
      )}
    </div>
  );
}
