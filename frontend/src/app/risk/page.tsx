"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { BarChart } from "@/components/charts/BarChart";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface EngineSummary {
  daily_pnl: number;
  current_capital: number;
  total_exposure: number;
  exposure_pct: number;
  drawdown: number;
  positions: Record<string, number>;
  total_positions: number;
  trade_count: number;
  kill_switch: boolean;
  daily_trades: Record<string, number>;
}

interface RiskStatus {
  account_value: number;
  daily_pnl: number;
  daily_loss_limit: number;
  daily_loss_used_pct: number;
  trades_today: number;
  max_daily_trades: number;
  open_positions: number;
  max_positions: number;
  total_exposure: number;
  exposure_pct: number;
  exposure_by_market: Record<string, number>;
  max_drawdown: number;
  kill_switch_active: boolean;
  risk_score: string;
  engine?: EngineSummary;
  limits: {
    max_daily_loss_pct: number;
    max_positions: number;
    max_position_size_pct: number;
    max_daily_trades: number;
  };
}

export default function RiskPage() {
  const { token, user } = useAuth();
  const [status, setStatus] = useState<RiskStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // editable limits
  const [maxDailyLoss, setMaxDailyLoss] = useState("5");
  const [maxPositions, setMaxPositions] = useState("10");
  const [maxPositionSize, setMaxPositionSize] = useState("10");
  const [maxDailyTrades, setMaxDailyTrades] = useState("20");

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const s = await api<RiskStatus>("/api/risk/status", { token });
      setStatus(s);
      setMaxDailyLoss(String(s.limits.max_daily_loss_pct));
      setMaxPositions(String(s.limits.max_positions));
      setMaxPositionSize(String(s.limits.max_position_size_pct));
      setMaxDailyTrades(String(s.limits.max_daily_trades));
      setError(null);
    } catch {
      setError("Could not load risk status");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    refresh();
  }, [token, refresh]);

  async function saveLimits(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api("/api/risk/limits", {
        method: "PUT",
        token,
        body: JSON.stringify({
          max_daily_loss_pct: Number(maxDailyLoss),
          max_positions: Number(maxPositions),
          max_position_size_pct: Number(maxPositionSize),
          max_daily_trades: Number(maxDailyTrades),
        }),
      });
      setNotice("Limits updated");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleKillSwitch() {
    if (!token || !status) return;
    setError(null);
    try {
      await api("/api/risk/kill-switch", {
        method: "POST",
        token,
        body: JSON.stringify({ active: !status.kill_switch_active }),
      });
      setNotice(status.kill_switch_active ? "Kill switch deactivated" : "KILL SWITCH ACTIVATED - trading blocked");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed");
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Risk Management</h1>
        <p className="text-sm text-text-muted">Loading risk status...</p>
      </div>
    );
  }

  const s = status;
  const exposureData = s && Object.keys(s.exposure_by_market).length > 0
    ? {
        labels: Object.keys(s.exposure_by_market),
        datasets: [{ label: "Exposure ($)", data: Object.values(s.exposure_by_market), color: "#4E8CFF" }],
      }
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Risk Management</h1>
        {s?.kill_switch_active && (
          <Badge variant="red" dot>KILL SWITCH ACTIVE</Badge>
        )}
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className={clsx("text-sm", notice.includes("ACTIVATED") ? "text-red" : "text-green")}>{notice}</p>}

      {s && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Daily P&L"
              value={`${s.daily_pnl >= 0 ? "+" : "-"}$${Math.abs(s.daily_pnl).toLocaleString()}`}
              change={`${s.daily_loss_used_pct}% of loss limit`}
            />
            <StatCard label="Open Positions" value={`${s.open_positions}/${s.max_positions}`} change={`${s.trades_today}/${s.max_daily_trades} trades today`} />
            <StatCard label="Risk Score" value={s.risk_score.toUpperCase()} />
            <StatCard label="Total Exposure" value={`$${s.total_exposure.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} change={`${s.exposure_pct}% of account`} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card>
              <CardHeader><CardTitle>Daily Loss Limit</CardTitle></CardHeader>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Used</span>
                  <span className="font-mono">${Math.max(-s.daily_pnl, 0).toLocaleString()} / ${s.daily_loss_limit.toLocaleString()}</span>
                </div>
                <div className="w-full h-3 bg-bg-tertiary rounded-full overflow-hidden">
                  <div
                    className={clsx("h-full rounded-full transition-all", s.daily_loss_used_pct >= 80 ? "bg-red" : s.daily_loss_used_pct >= 50 ? "bg-yellow" : "bg-green")}
                    style={{ width: `${Math.min(s.daily_loss_used_pct, 100)}%` }}
                  />
                </div>
                <p className="text-xs text-text-muted">{(100 - Math.min(s.daily_loss_used_pct, 100)).toFixed(0)}% of limit remaining today</p>
              </div>
            </Card>

            <DrawdownCard accountValue={s.account_value} maxDrawdown={s.max_drawdown} engine={s.engine} />

            <EngineCard engine={s.engine} />
          </div>

          <Card>
            <CardHeader><CardTitle>Exposure by Market</CardTitle></CardHeader>
            {exposureData
              ? <BarChart data={exposureData} height={200} />
              : <p className="text-sm text-text-muted py-8 text-center">No open exposure.</p>}
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card>
              <CardHeader><CardTitle>Risk Limits</CardTitle></CardHeader>
              <form onSubmit={saveLimits} className="space-y-4">
                <Input
                  label="Max Daily Loss (% of account)"
                  type="number" min="0.1" step="0.1"
                  value={maxDailyLoss}
                  onChange={(e) => setMaxDailyLoss(e.target.value)}
                  required
                />
                <Input
                  label="Max Open Positions"
                  type="number" min="1" step="1"
                  value={maxPositions}
                  onChange={(e) => setMaxPositions(e.target.value)}
                  required
                />
                <Input
                  label="Max Position Size (% of account)"
                  type="number" min="0.5" step="0.5"
                  value={maxPositionSize}
                  onChange={(e) => setMaxPositionSize(e.target.value)}
                  required
                />
                <Input
                  label="Max Trades Per Day"
                  type="number" min="1" step="1"
                  value={maxDailyTrades}
                  onChange={(e) => setMaxDailyTrades(e.target.value)}
                  required
                />
                <Button type="submit" disabled={saving} className="w-full">
                  {saving ? "Saving..." : "Save Limits"}
                </Button>
              </form>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader><CardTitle>Kill Switch</CardTitle></CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
                <div>
                  <p className="text-sm text-text-secondary">
                    {s.kill_switch_active
                      ? "All new orders are blocked. Disable to resume trading."
                      : "Instantly block all new orders in an emergency."}
                  </p>
                  <p className="text-xs text-text-muted mt-1">
                    Account value ${s.account_value.toLocaleString(undefined, { minimumFractionDigits: 2 })} · Max drawdown ${Math.abs(s.max_drawdown).toLocaleString()}
                  </p>
                </div>
                <Button
                  variant={s.kill_switch_active ? "secondary" : "danger"}
                  onClick={toggleKillSwitch}
                >
                  {s.kill_switch_active ? "Deactivate Kill Switch" : "Activate Kill Switch"}
                </Button>
              </div>
              {user?.is_admin && (
                <p className="text-xs text-text-muted mt-4 border-t border-border pt-3">
                  Admin: your toggle also controls the shared cross-market engine switch.
                </p>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function DrawdownCard({ accountValue, maxDrawdown, engine }: { accountValue: number; maxDrawdown: number; engine?: EngineSummary }) {
  const ddUsd = Math.abs(Math.min(maxDrawdown, 0));
  const ddPctOfAccount = accountValue > 0 ? (ddUsd / accountValue) * 100 : 0;
  const pctOfCap = Math.min((ddPctOfAccount / 10) * 100, 100);
  const engineDdPct = engine ? engine.drawdown * 100 : null;

  return (
    <Card>
      <CardHeader><CardTitle>Max Drawdown</CardTitle></CardHeader>
      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-text-secondary">Peak-to-trough</span>
          <span className="font-mono text-red">-${ddUsd.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
        </div>
        <div className="w-full h-3 bg-bg-tertiary rounded-full overflow-hidden">
          <div
            className={clsx("h-full rounded-full transition-all", pctOfCap >= 80 ? "bg-red" : pctOfCap >= 50 ? "bg-yellow" : "bg-green")}
            style={{ width: `${pctOfCap}%` }}
          />
        </div>
        <p className="text-xs text-text-muted">
          {ddPctOfAccount.toFixed(1)}% of account · auto trip at 10%
          {engineDdPct !== null && <> · engine: {engineDdPct.toFixed(1)}%</>}
        </p>
      </div>
    </Card>
  );
}

function EngineCard({ engine }: { engine?: EngineSummary }) {
  if (!engine) {
    return (
      <Card>
        <CardHeader><CardTitle>Cross-Market Engine</CardTitle></CardHeader>
        <p className="text-sm text-text-muted py-8 text-center">Engine state unavailable.</p>
      </Card>
    );
  }

  const tradesTotal = Object.values(engine.daily_trades).reduce((a, b) => a + b, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cross-Market Engine</CardTitle>
      </CardHeader>
      <div className="space-y-3">
        {engine.kill_switch
          ? <Badge variant="red" dot>KILL SWITCH ACTIVE</Badge>
          : <Badge variant="green" dot>OPERATIONAL</Badge>}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className={clsx("text-sm font-mono font-semibold", engine.daily_pnl >= 0 ? "text-green" : "text-red")}>
              {engine.daily_pnl >= 0 ? "+" : "-"}${Math.abs(engine.daily_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
            <p className="text-xs text-text-muted">Daily P&L</p>
          </div>
          <div>
            <p className="text-sm font-mono font-semibold">{engine.total_positions}</p>
            <p className="text-xs text-text-muted">Positions</p>
          </div>
          <div>
            <p className="text-sm font-mono font-semibold">{tradesTotal}</p>
            <p className="text-xs text-text-muted">Trades Today</p>
          </div>
        </div>
        <div className="space-y-1.5 border-t border-border pt-3">
          {Object.entries(engine.positions).map(([market, count]) => (
            <div key={market} className="flex items-center justify-between text-xs">
              <span className="text-text-secondary capitalize">{market}</span>
              <span className="font-mono">{count} pos · {engine.daily_trades[market] ?? 0} trades today</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
