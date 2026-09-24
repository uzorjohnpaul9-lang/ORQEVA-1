"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { DiscoveryCoin, MarketOverview } from "@/lib/types";

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (v >= 10) return v.toFixed(2);
  return v.toFixed(4);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export default function MarketPage() {
  const { token } = useAuth();
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [coins, setCoins] = useState<DiscoveryCoin[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string>("");
  const [error, setError] = useState<string>("");

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [o, d] = await Promise.all([
        api<MarketOverview>("/api/market/overview", { token }),
        api<{ coins: DiscoveryCoin[] }>("/api/market/discovery?top_n=8", { token }),
      ]);
      setOverview(o);
      setCoins(d.coins || []);
      setUpdatedAt(new Date().toLocaleTimeString());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load market data");
    }
  }, [token]);

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  const indices = overview?.indices ?? [];
  const gainers = overview?.movers?.gainers ?? [];
  const losers = overview?.movers?.losers ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Market Overview</h1>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Badge variant="green" dot>LIVE</Badge>
          {updatedAt && <span>Updated {updatedAt}</span>}
        </div>
      </div>

      {error && (
        <Card><p className="text-sm text-red-400">{error}</p></Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {indices.length === 0 && !error && (
          <Card><p className="text-sm text-text-muted">Loading market data...</p></Card>
        )}
        {indices.map((idx) => {
          const up = (idx.change_percent ?? 0) >= 0;
          return (
            <Card key={`${idx.market}-${idx.symbol}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{idx.label}</p>
                  <p className="text-xs text-text-muted">{idx.symbol}</p>
                </div>
                {idx.change_percent != null && (
                  <Badge variant={up ? "green" : "red"}>{fmtPct(idx.change_percent)}</Badge>
                )}
              </div>
              <p className="text-xl font-bold mt-2 font-mono">{fmtPrice(idx.price)}</p>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle>Top Gainers</CardTitle></CardHeader>
          <div className="space-y-1">
            {gainers.length === 0 && <p className="text-sm text-text-muted">No data</p>}
            {gainers.map((m) => (
              <div key={m.symbol} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <p className="text-sm font-medium">{m.symbol}</p>
                <div className="text-right">
                  <p className="text-sm font-mono">{fmtPrice(m.price)}</p>
                  <p className="text-xs text-green">{fmtPct(m.change_percent)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader><CardTitle>Top Losers</CardTitle></CardHeader>
          <div className="space-y-1">
            {losers.length === 0 && <p className="text-sm text-text-muted">No data</p>}
            {losers.map((m) => (
              <div key={m.symbol} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <p className="text-sm font-medium">{m.symbol}</p>
                <div className="text-right">
                  <p className="text-sm font-mono">{fmtPrice(m.price)}</p>
                  <p className="text-xs text-red-400">{fmtPct(m.change_percent)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader><CardTitle>Crypto Discovery</CardTitle></CardHeader>
          <div className="space-y-1">
            {coins.length === 0 && <p className="text-sm text-text-muted">No scan results yet — run a discovery scan</p>}
            {coins.map((c) => (
              <div key={c.symbol} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <div>
                  <p className="text-sm font-medium">{c.symbol}</p>
                  <p className="text-xs text-text-muted">RSI {c.rsi} · score {c.score}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-mono">{fmtPrice(c.price)}</p>
                  {c.direction && (
                    <Badge variant={c.direction === "buy" ? "green" : "red"}>{c.direction.toUpperCase()}</Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
