"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { CandleChart, type CandleBar, type PriceLine } from "@/components/charts/CandleChart";

const MARKETS = ["crypto", "stock", "forex", "commodity"] as const;
const INTERVALS = ["5min", "15min", "30min", "1h", "1day", "1week"] as const;

type Market = (typeof MARKETS)[number];
type Interval = (typeof INTERVALS)[number];

const DEFAULT_SYMBOL: Record<Market, string> = {
  crypto: "BTC/USD",
  stock: "AAPL",
  forex: "EUR/USD",
  commodity: "XAU/USD",
};

interface IndicatorsResponse {
  symbol: string;
  interval: string;
  bars: CandleBar[];
  indicators: { ema9: (number | null)[]; ema21: (number | null)[]; ema50: (number | null)[] };
  error?: string;
}

function last(arr: (number | null)[] | undefined): number | null {
  if (!arr || arr.length === 0) return null;
  for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return arr[i] as number;
  return null;
}

function fmt(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return v.toFixed(4);
}

function num(v: string | null): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function ChartsInner() {
  const { token } = useAuth();
  const params = useSearchParams();

  const qMarket = params.get("market");
  const qInterval = params.get("interval");
  const qSymbol = params.get("symbol");
  const qEntry = num(params.get("entry"));
  const qSl = num(params.get("sl"));
  const qTp = num(params.get("tp"));
  const qSide = params.get("side");

  const tradeMode = qEntry != null;

  const initialMarket: Market = (MARKETS as readonly string[]).includes(qMarket ?? "")
    ? (qMarket as Market)
    : "crypto";
  const initialInterval: Interval = (INTERVALS as readonly string[]).includes(qInterval ?? "")
    ? (qInterval as Interval)
    : "1day";

  const [market, setMarket] = useState<Market>(initialMarket);
  const [symbol, setSymbol] = useState(qSymbol?.trim() || DEFAULT_SYMBOL[initialMarket]);
  const [interval, setInterval] = useState<Interval>(initialInterval);
  const [data, setData] = useState<IndicatorsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!token || !symbol.trim()) return;
    setLoading(true);
    try {
      const r = await api<IndicatorsResponse>(
        `/api/market/indicators?symbol=${encodeURIComponent(symbol.trim())}&market=${market}&interval=${interval}&outputsize=120`,
        { token }
      );
      if (r.error) {
        setError(r.error);
        setData(null);
      } else {
        setData(r);
        setError("");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chart");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [token, symbol, market, interval]);

  useEffect(() => {
    load();
  }, [load]);

  const pickMarket = (m: Market) => {
    setMarket(m);
    setSymbol(DEFAULT_SYMBOL[m]);
  };

  const e9 = last(data?.indicators.ema9);
  const e21 = last(data?.indicators.ema21);
  const e50 = last(data?.indicators.ema50);
  const price = data?.bars?.length ? data.bars[data.bars.length - 1].close : null;
  const bias =
    e9 != null && e21 != null && e50 != null
      ? e9 > e21 && e21 > e50
        ? "bullish"
        : e9 < e21 && e21 < e50
          ? "bearish"
          : "mixed"
      : "—";

  const lines = useMemo<PriceLine[]>(() => {
    if (!tradeMode) return [];
    const out: PriceLine[] = [];
    if (qEntry != null) out.push({ price: qEntry, label: "Entry", color: "#4C6FFF" });
    if (qSl != null) out.push({ price: qSl, label: "Stop", color: "#FF4757", dashed: true });
    if (qTp != null) out.push({ price: qTp, label: "Target", color: "#00D68F", dashed: true });
    return out;
  }, [tradeMode, qEntry, qSl, qTp]);

  const dir = qSide === "sell" || qSide === "short" ? -1 : 1;
  const ret =
    tradeMode && price != null && qEntry
      ? ((price - qEntry) / qEntry) * dir * 100
      : null;
  const inProfit = ret != null && ret >= 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Charts</h1>
          <p className="text-sm text-text-secondary mt-1">
            Candlesticks with EMA 9 / 21 / 50 — the same EMAs that feed the signal engines.
          </p>
        </div>
        <Badge variant={bias === "bullish" ? "green" : bias === "bearish" ? "red" : "gray"}>
          EMA trend: {bias}
        </Badge>
      </div>

      {tradeMode && (
        <Card className={clsx(inProfit ? "border-green/40" : "border-red/40")}>
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
            <div>
              <p className="text-[10px] text-text-muted uppercase tracking-wider">Position</p>
              <p className="font-semibold mt-0.5">
                {symbol} <span className={dir === 1 ? "text-green" : "text-red"}>{dir === 1 ? "LONG" : "SHORT"}</span>
              </p>
            </div>
            {[
              { label: "Entry", value: qEntry },
              { label: "Stop", value: qSl },
              { label: "Target", value: qTp },
              { label: "Now", value: price },
            ].map((r) => (
              <div key={r.label}>
                <p className="text-[10px] text-text-muted uppercase tracking-wider">{r.label}</p>
                <p className="font-mono text-sm mt-0.5">{fmt(r.value)}</p>
              </div>
            ))}
            <div className="ml-auto text-right">
              <p className="text-[10px] text-text-muted uppercase tracking-wider">Unrealized</p>
              <p className={clsx("font-mono text-lg font-bold", inProfit ? "text-green" : "text-red")}>
                {ret != null ? `${inProfit ? "+" : ""}${ret.toFixed(2)}%` : "—"}
              </p>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-2">
          {MARKETS.map((m) => (
            <button
              key={m}
              onClick={() => pickMarket(m)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                market === m ? "bg-green text-bg-primary" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
              )}
            >
              {m.toUpperCase()}
            </button>
          ))}
          <span className="w-px h-5 bg-border mx-1" />
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") load();
            }}
            placeholder="Symbol"
            className="w-32 bg-bg-tertiary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-green/50"
          />
          <select
            value={interval}
            onChange={(e) => setInterval(e.target.value as Interval)}
            className="bg-bg-tertiary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary outline-none focus:border-green/50"
          >
            {INTERVALS.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
          <button
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue text-white hover:bg-blue/90 transition-colors disabled:opacity-50"
          >
            {loading ? "Loading…" : "Load"}
          </button>
        </div>
      </Card>

      {error && (
        <Card>
          <p className="text-sm text-red-400">
            {error === "no_api_key"
              ? "No market-data key configured for this market."
              : `Couldn't load chart: ${error}`}
          </p>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            {data ? `${data.symbol} · ${data.interval}` : "Chart"}
            {price != null && <span className="ml-2 font-mono text-text-secondary">{fmt(price)}</span>}
          </CardTitle>
        </CardHeader>
        {data && data.bars.length > 0 ? (
          <CandleChart
            bars={data.bars}
            ema9={data.indicators.ema9}
            ema21={data.indicators.ema21}
            ema50={data.indicators.ema50}
            lines={lines}
          />
        ) : (
          !error && <p className="text-sm text-text-muted">{loading ? "Loading chart…" : "No data."}</p>
        )}
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: "EMA 9", value: e9, color: "#FFBE0B" },
          { label: "EMA 21", value: e21, color: "#4C6FFF" },
          { label: "EMA 50", value: e50, color: "#B14CFF" },
        ].map((row) => (
          <Card key={row.label}>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: row.color }} />
                {row.label}
              </span>
              <span className="font-mono text-sm">{fmt(row.value)}</span>
            </div>
          </Card>
        ))}
      </div>

      <p className="text-xs text-text-muted">Educational tool — not financial advice.</p>
    </div>
  );
}

export default function ChartsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-text-muted">Loading chart…</p>}>
      <ChartsInner />
    </Suspense>
  );
}
