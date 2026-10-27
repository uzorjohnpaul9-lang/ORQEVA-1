"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Reveal } from "@/components/motion/Reveal";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart } from "@/components/charts/BarChart";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AccuracyStats } from "@/lib/types";

interface Analytics {
  range: { start: string | null; end: string | null };
  closed_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  pnl_series: { date: string; pnl: number; equity: number }[];
  drawdown_series: { date: string; drawdown: number; drawdown_pct: number }[];
  by_strategy: { strategy: string; wins: number; losses: number; win_rate: number; total_pnl: number }[];
  correlation: { markets: string[]; matrix: number[][]; note?: string };
}

const RANGES = [
  { value: "7", label: "7D" },
  { value: "30", label: "30D" },
  { value: "90", label: "90D" },
  { value: "", label: "All" },
];

function corrColor(v: number): string {
  if (v >= 0.5) return "text-green";
  if (v <= -0.5) return "text-red";
  return "text-text-secondary";
}

export default function AnalyticsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState("30");
  const [signalStats, setSignalStats] = useState<AccuracyStats | null>(null);
  const [signalLoading, setSignalLoading] = useState(true);
  const [signalError, setSignalError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    (async () => {
      try {
        const qs = range ? `?days=${range}` : "";
        const d = await api<Analytics>(`/api/trading/analytics${qs}`, { token });
        if (active) { setData(d); setError(null); }
      } catch {
        if (active) setError("Could not load analytics");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [token, range]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setSignalLoading(true);
    api<AccuracyStats>("/api/signals/accuracy", { token })
      .then((d) => { if (active) { setSignalStats(d); setSignalError(null); } })
      .catch(() => { if (active) setSignalError("Could not load signal outcomes"); })
      .finally(() => { if (active) setSignalLoading(false); });
    return () => { active = false; };
  }, [token]);

  const equityData = useMemo(
    () => data && {
      labels: data.pnl_series.map((p) => p.date),
      datasets: [{ label: "Equity", data: data.pnl_series.map((p) => p.equity), color: "#00D68F" }],
    },
    [data]
  );

  const dailyPnlData = useMemo(
    () => data && {
      labels: data.pnl_series.map((p) => p.date),
      datasets: [{ label: "Daily P&L", data: data.pnl_series.map((p) => p.pnl), color: "#3B82F6" }],
    },
    [data]
  );

  const drawdownData = useMemo(
    () => data && {
      labels: data.drawdown_series.map((d) => d.date),
      datasets: [{ label: "Drawdown", data: data.drawdown_series.map((d) => d.drawdown), color: "#FF4757" }],
    },
    [data]
  );

  const strategyData = useMemo(
    () => data && {
      labels: data.by_strategy.map((s) => s.strategy),
      datasets: [{ label: "Win Rate %", data: data.by_strategy.map((s) => s.win_rate), color: "#FFBE0B" }],
    },
    [data]
  );

  const marketWinRateData = useMemo(() => {
    if (!signalStats || signalStats.markets.length === 0) return undefined;
    return {
      labels: signalStats.markets.map((m) => m.market),
      datasets: [{ label: "Win Rate %", data: signalStats.markets.map((m) => m.win_rate), color: "#00D68F" }],
    };
  }, [signalStats]);

  const outcomes = signalStats?.outcomes;
  const hasOutcomes = !!outcomes && outcomes.resolved > 0;

  const marketHitRateData = useMemo(() => {
    if (!outcomes || outcomes.by_market.length === 0) return undefined;
    return {
      labels: outcomes.by_market.map((m) => m.market),
      datasets: [{ label: "Hit Rate %", data: outcomes.by_market.map((m) => m.win_rate), color: "#00D68F" }],
    };
  }, [outcomes]);

  async function exportCsv() {
    if (!token || !data) return;
    try {
      const qs = range ? `?days=${range}` : "";
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001"}/api/trading/export${qs}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `trades_${range || "all"}d.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export failed");
    }
  }

  return (
    <Reveal className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-text-secondary mt-1">Performance charts and cross-market analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-bg-tertiary rounded-lg border border-border overflow-hidden">
            {RANGES.map((r) => (
              <button
                key={r.value}
                onClick={() => setRange(r.value)}
                className={clsx(
                  "px-3 py-1.5 text-xs font-medium transition-colors",
                  range === r.value ? "bg-green text-bg-primary" : "text-text-secondary hover:text-text-primary"
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
          <Button variant="secondary" size="sm" onClick={exportCsv}>Export CSV</Button>
        </div>
      </div>

      {/* Signal Outcomes — platform-wide, primary */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Signal Outcomes</h2>
          <p className="text-sm text-text-secondary mt-1">Platform-wide accuracy across all closed signals</p>
        </div>

        {signalLoading && <p className="text-sm text-text-muted">Loading signal outcomes...</p>}
        {signalError && <p className="text-sm text-red">{signalError}</p>}

        {!signalLoading && !signalError && signalStats && (
          !hasOutcomes && signalStats.overall.closed_trades === 0 ? (
            <Card>
              <p className="text-sm text-text-muted py-6 text-center">
                No resolved signal outcomes yet — platform accuracy appears here as signals hit their targets or stops.
              </p>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  label="Total Signals"
                  value={signalStats.signals.total_signals.toLocaleString()}
                  change={`${signalStats.signals.active_signals} active`}
                />
                <StatCard
                  label="Signal Hit Rate"
                  value={hasOutcomes ? `${outcomes!.win_rate}%` : `${signalStats.overall.win_rate}%`}
                  change={hasOutcomes ? `${outcomes!.resolved} resolved` : `${signalStats.overall.closed_trades} closed`}
                />
                {hasOutcomes ? (
                  <StatCard
                    label="Avg R Multiple"
                    value={`${outcomes!.avg_r >= 0 ? "+" : ""}${outcomes!.avg_r.toFixed(2)}R`}
                    change={`${outcomes!.by_outcome.tp ?? 0} TP / ${outcomes!.by_outcome.sl ?? 0} SL`}
                  />
                ) : (
                  <StatCard
                    label="Signal P&L"
                    value={`${signalStats.overall.total_pnl >= 0 ? "+" : "-"}$${Math.abs(signalStats.overall.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
                  />
                )}
                <StatCard
                  label="Markets Tracked"
                  value={(hasOutcomes ? outcomes!.by_market.length : signalStats.markets.length).toString()}
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader><CardTitle>Hit Rate by Market</CardTitle></CardHeader>
                  {(hasOutcomes ? marketHitRateData : marketWinRateData)
                    ? <BarChart data={(hasOutcomes ? marketHitRateData : marketWinRateData)!} height={250} />
                    : <p className="text-sm text-text-muted py-8 text-center">No market outcomes yet.</p>}
                </Card>
                <Card padding={false}>
                  <div className="px-4 pt-4"><CardTitle>Signal Outcomes by Market</CardTitle></div>
                  <div className="px-4 pb-4 mt-3 overflow-x-auto">
                    <table className="w-full text-sm min-w-[420px]">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left text-xs text-text-muted uppercase py-2 px-4">Market</th>
                          <th className="text-center text-xs text-text-muted uppercase py-2 px-4">{hasOutcomes ? "Resolved" : "Closed"}</th>
                          <th className="text-center text-xs text-text-muted uppercase py-2 px-4">W</th>
                          <th className="text-center text-xs text-text-muted uppercase py-2 px-4">L</th>
                          <th className="text-center text-xs text-text-muted uppercase py-2 px-4">Hit %</th>
                          {!hasOutcomes && <th className="text-right text-xs text-text-muted uppercase py-2 px-4">P&L</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {hasOutcomes
                          ? outcomes!.by_market.map((m) => (
                              <tr key={m.market} className="border-b border-border/50 last:border-0">
                                <td className="capitalize px-4 py-2.5">{m.market}</td>
                                <td className="text-center px-4 py-2.5">{m.resolved}</td>
                                <td className="text-center px-4 py-2.5 text-green">{m.wins}</td>
                                <td className="text-center px-4 py-2.5 text-red">{m.resolved - m.wins}</td>
                                <td className="text-center px-4 py-2.5 font-mono">{m.win_rate}%</td>
                              </tr>
                            ))
                          : signalStats.markets.map((m) => (
                              <tr key={m.market} className="border-b border-border/50 last:border-0">
                                <td className="capitalize px-4 py-2.5">{m.market}</td>
                                <td className="text-center px-4 py-2.5">{m.closed_trades}</td>
                                <td className="text-center px-4 py-2.5 text-green">{m.wins}</td>
                                <td className="text-center px-4 py-2.5 text-red">{m.losses}</td>
                                <td className="text-center px-4 py-2.5 font-mono">{m.win_rate}%</td>
                                <td className={clsx("text-right px-4 py-2.5 font-mono", m.total_pnl >= 0 ? "text-green" : "text-red")}>
                                  {m.total_pnl >= 0 ? "+" : "-"}${Math.abs(m.total_pnl).toLocaleString()}
                                </td>
                              </tr>
                            ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>

              {(outcomes!.live > 0 || outcomes!.simulated > 0 || outcomes!.unknown > 0) && (
                <p className="text-xs text-text-muted">
                  Data source across resolved signals: {outcomes!.live} live
                  {outcomes!.simulated > 0 ? `, ${outcomes!.simulated} simulated (included for reference)` : ""}
                  {outcomes!.unknown > 0 ? `, ${outcomes!.unknown} unclassified` : ""}.
                </p>
              )}
            </>
          )
        )}
      </section>

      {/* Your Trades — personal */}
      <div className="pt-2">
        <h2 className="text-lg font-semibold">Your Trades</h2>
        <p className="text-sm text-text-secondary mt-1">
          Your personal trading performance{range ? ` · last ${range} days` : " · all time"}
        </p>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {loading && <p className="text-sm text-text-muted">Loading analytics...</p>}

      {!loading && !error && data && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Cumulative Equity</CardTitle></CardHeader>
              {equityData && equityData.labels.length > 0
                ? <LineChart data={equityData} height={250} />
                : <p className="text-sm text-text-muted py-8 text-center">No closed trades in range.</p>}
            </Card>
            <Card>
              <CardHeader><CardTitle>Daily P&L</CardTitle></CardHeader>
              {dailyPnlData && dailyPnlData.labels.length > 0
                ? <BarChart data={dailyPnlData} height={250} />
                : <p className="text-sm text-text-muted py-8 text-center">No closed trades in range.</p>}
            </Card>
            <Card>
              <CardHeader><CardTitle>Drawdown</CardTitle></CardHeader>
              {drawdownData && drawdownData.labels.length > 0
                ? <LineChart data={drawdownData} height={250} />
                : <p className="text-sm text-text-muted py-8 text-center">No closed trades in range.</p>}
            </Card>
            <Card>
              <CardHeader><CardTitle>Win Rate by Strategy</CardTitle></CardHeader>
              {strategyData && strategyData.labels.length > 0
                ? <BarChart data={strategyData} height={250} />
                : <p className="text-sm text-text-muted py-8 text-center">No closed trades in range.</p>}
            </Card>
          </div>

          <Card padding={false}>
            <div className="px-4 pt-4">
              <CardTitle>Market Correlation (daily P&L)</CardTitle>
            </div>
            <div className="px-4 pb-4 mt-3 overflow-x-auto">
              {data.correlation.markets.length >= 2 ? (
                <table className="w-full text-sm min-w-[540px]">
                  <thead>
                    <tr>
                      <th className="text-left text-xs text-text-muted uppercase py-2 px-3"></th>
                      {data.correlation.markets.map((m) => (
                        <th key={m} className="text-xs text-text-muted uppercase py-2 px-3">{m}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.correlation.matrix.map((row, i) => (
                      <tr key={data.correlation.markets[i]}>
                        <td className="py-2 px-3 text-xs text-text-muted uppercase">{data.correlation.markets[i]}</td>
                        {row.map((v, j) => (
                          <td key={j} className={clsx("py-2 px-3 text-center font-mono", corrColor(v))}>
                            {v.toFixed(2)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-text-muted py-4">
                  {data.correlation.note || "Need trades in at least two markets."}
                </p>
              )}
            </div>
          </Card>
        </>
      )}
    </Reveal>
  );
}
