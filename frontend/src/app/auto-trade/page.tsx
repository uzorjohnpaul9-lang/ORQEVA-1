"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AutoTradeLogEntry, AutoTradeSettings } from "@/lib/types";

const MARKET_CHIPS = [
  { market: "forex", label: "Forex", tier: "Free" },
  { market: "stock", label: "Stock", tier: "Premium" },
  { market: "crypto", label: "Crypto", tier: "VIP" },
];

const STATUS_VARIANT: Record<string, "green" | "red" | "blue" | "yellow" | "gray"> = {
  placed: "green",
  skipped: "gray",
  rejected: "yellow",
  error: "red",
};

export default function AutoTradePage() {
  const { token, user } = useAuth();
  const [settings, setSettings] = useState<AutoTradeSettings | null>(null);
  const [log, setLog] = useState<AutoTradeLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [s, l] = await Promise.all([
        api<AutoTradeSettings>("/api/auto-trade/settings", { token }),
        api<{ entries: AutoTradeLogEntry[] }>("/api/auto-trade/log?limit=50", { token }),
      ]);
      setSettings(s);
      setLog(l.entries || []);
      setError(null);
    } catch {
      setError("Could not load auto-trade settings");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    refresh();
  }, [token, refresh]);

  async function save(next: AutoTradeSettings) {
    if (!token) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      setSettings(await api<AutoTradeSettings>("/api/auto-trade/settings", {
        method: "PUT",
        token,
        body: JSON.stringify(next),
      }));
      setNotice(next.enabled ? "Auto-Trade enabled - the AI will act on the next market scan" : "Auto-Trade disabled");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  function toggleMarket(market: string) {
    if (!settings) return;
    const has = settings.markets.includes(market);
    const markets = has ? settings.markets.filter((m) => m !== market) : [...settings.markets, market];
    save({ ...settings, markets });
  }

  const placed = log.filter((e) => e.status === "placed").length;
  const trimmed = settings
    ? settings.markets.map((m) => MARKET_CHIPS.find((c) => c.market === m)?.label ?? m)
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI Auto-Trade</h1>
        <p className="text-sm text-text-secondary mt-1">
          Let the engine run your trades - every signal it publishes can be opened for you automatically.
        </p>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Status" value={settings?.enabled ? "Active" : "Off"} />
        <StatCard label="Auto Orders" value={placed.toString()} />
        <StatCard label="Markets" value={trimmed.length ? trimmed.join(" · ") : "None"} />
      </div>

      {loading ? (
        <Card><p className="text-sm text-text-muted">Loading...</p></Card>
      ) : settings ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Master Control</CardTitle>
              </CardHeader>
              <div className="space-y-4">
                <Button
                  variant={settings.enabled ? "secondary" : "primary"}
                  className="w-full"
                  disabled={saving}
                  onClick={() => save({ ...settings, enabled: !settings.enabled })}
                >
                  {settings.enabled ? "Disable Auto-Trade" : "Enable Auto-Trade"}
                </Button>
                <Select
                  label="Route"
                  value={settings.route}
                  options={[
                    { value: "paper", label: "Paper (simulated)" },
                    { value: "live", label: "Live (broker)" },
                  ]}
                  onChange={(e) => save({ ...settings, route: e.target.value as "paper" | "live" })}
                />
                {settings.route === "live" && (
                  <p className="text-xs text-text-muted">
                    The AI will only trade live when you have a validated broker connection for that market on the{" "}
                    <Link href="/exchanges" className="text-green underline">Exchanges</Link> page. Otherwise the
                    attempt is skipped and logged.
                  </p>
                )}
                <Input
                  label="Risk per trade (%)"
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={settings.per_trade_risk_pct}
                  onChange={(e) =>
                    save({ ...settings, per_trade_risk_pct: Math.max(0.1, Math.min(10, Number(e.target.value) || 1)) })
                  }
                  disabled={saving}
                />
                <Input
                  label="Min confidence"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={settings.min_confidence}
                  onChange={(e) =>
                    save({ ...settings, min_confidence: Math.max(0, Math.min(1, Number(e.target.value) || 0)) })
                  }
                  disabled={saving}
                />
              </div>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Markets</CardTitle>
              </CardHeader>
              <div className="space-y-2">
                {MARKET_CHIPS.map((c) => {
                  const active = settings.markets.includes(c.market);
                  return (
                    <button
                      key={c.market}
                      onClick={() => toggleMarket(c.market)}
                      disabled={saving}
                      className={`w-full flex items-center justify-between px-4 py-3 rounded-lg border text-sm transition-colors ${
                        active
                          ? "bg-green/10 border-green/40 text-text-primary"
                          : "bg-bg-tertiary border-border text-text-secondary hover:bg-bg-hover"
                      }`}
                    >
                      <span>{c.label}</span>
                      <Badge variant={active ? "green" : "gray"}>{c.tier}</Badge>
                    </button>
                  );
                })}
              </div>
              {user?.tier && user.tier !== "vip" && (
                <p className="text-xs text-text-muted mt-3">
                  Crypto signals need VIP tier; stock needs Premium. Upgrade under{" "}
                  <Link href="/vip" className="text-green underline">Plans</Link>.
                </p>
              )}
            </Card>
          </div>

          <div className="lg:col-span-2">
            <Card padding={false}>
              <div className="px-4 pt-4">
                <CardTitle>Auto-Trade Ledger</CardTitle>
                <p className="text-xs text-text-muted mt-1">
                  Every signal the AI evaluated, and what it did about it.
                </p>
              </div>
              <div className="mt-2 divide-y divide-border/50">
                {log.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-text-muted">
                    No auto-trade attempts yet. Enable Auto-Trade and the next market scan will begin the ledger.
                  </p>
                ) : (
                  log.map((e) => (
                    <div key={e.id} className="flex items-start justify-between gap-3 px-4 py-3 text-sm">
                      <div className="flex items-center gap-2">
                        <Badge variant={e.direction === "buy" ? "green" : "red"}>{e.direction.toUpperCase()}</Badge>
                        <span className="font-medium">{e.symbol}</span>
                        <span className="text-text-muted capitalize">{e.market}</span>
                        {e.quantity && <span className="font-mono text-xs text-text-muted">{e.quantity}</span>}
                        {e.entry_price && <span className="font-mono text-xs text-text-muted">@{e.entry_price}</span>}
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <div className="flex items-center gap-2">
                          <Badge variant={e.route === "live" ? "blue" : "gray"}>{e.route}</Badge>
                          <Badge variant={STATUS_VARIANT[e.status]}>{e.status.toUpperCase()}</Badge>
                        </div>
                        {e.reason && e.reason !== "ok" && (
                          <span className="text-xs text-text-muted max-w-xs text-right">{e.reason}</span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}