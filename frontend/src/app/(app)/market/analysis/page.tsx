"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface RegimeInfo {
  regime: string;
  description: string;
  confidence: number;
  recommendation: string;
}

interface MomentumInfo {
  overall: string;
  short_term_pct: number;
  medium_term_pct: number;
  long_term_pct: number;
  acceleration_pct: number;
  score: number;
}

interface AnalysisResult {
  symbol: string;
  market: string;
  bars_used?: number;
  current_price?: number;
  regime?: RegimeInfo;
  momentum?: MomentumInfo;
  volatility?: { daily_pct: number; annualized_pct: number };
  confidence?: { score: number; breakdown: Record<string, number>; recommendation: string };
  error?: string;
}

interface SummaryMarket {
  market: string;
  error?: string;
  regime?: RegimeInfo;
  current_price?: number;
  confidence?: { score: number };
}

interface ModelInfo {
  name: string;
  key: string;
  description: string;
  kind: string;
}

const REGIME_VARIANT: Record<string, "green" | "red" | "yellow" | "blue"> = {
  bull: "green",
  bear: "red",
  sideways: "yellow",
  volatile: "blue",
};

const MOMENTUM_VARIANT: Record<string, "green" | "red" | "yellow" | "purple"> = {
  strong_bullish: "green",
  bullish: "green",
  neutral: "yellow",
  bearish: "red",
  strong_bearish: "red",
};

const MARKET_LABEL: Record<string, string> = {
  stock: "Stocks",
  crypto: "Crypto",
  forex: "Forex",
};

export default function AIAnalysisPage() {
  const { token } = useAuth();
  const [markets, setMarkets] = useState<SummaryMarket[] | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  // symbol analysis form
  const [symbol, setSymbol] = useState("NVDA");
  const [market, setMarket] = useState("stock");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!token) return;
    try {
      const s = await api<{ markets: SummaryMarket[]; models: ModelInfo[] }>("/api/ai/summary", { token });
      setMarkets(s.markets);
      setModels(s.models);
      setError(null);
    } catch {
      setError("Could not load AI summary");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    loadSummary();
  }, [token, loadSummary]);

  async function runAnalysis(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const a = await api<AnalysisResult>(
        `/api/ai/analysis?symbol=${encodeURIComponent(symbol)}&market=${market}`,
        { token }
      );
      if (a.error) {
        setError(`Analysis unavailable: ${a.error}`);
        setAnalysis(null);
      } else {
        setAnalysis(a);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">AI Analysis</h1>
        <Button variant="secondary" size="sm" onClick={loadSummary}>Refresh</Button>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}

      {/* Market regimes */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(markets ?? [{ market: "stock" }, { market: "crypto" }, { market: "forex" }]).map((m) => (
          <Card key={m.market}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">{MARKET_LABEL[m.market] ?? m.market}</h3>
              {m.regime ? (
                <Badge variant={REGIME_VARIANT[m.regime.regime] ?? "gray"}>{m.regime.description}</Badge>
              ) : (
                <Badge variant="gray">no data</Badge>
              )}
            </div>
            {m.regime ? (
              <div className="space-y-2 text-sm">
                <p className="text-text-secondary">{m.regime.recommendation}</p>
                <div className="flex justify-between text-xs text-text-muted">
                  <span>{m.current_price != null && `$${m.current_price.toLocaleString()}`}</span>
                  <span>confidence {(m.confidence?.score ?? m.regime.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-text-muted py-4 text-center">Live data unavailable.</p>
            )}
          </Card>
        ))}
      </div>

      {/* Symbol analyzer */}
      <Card>
        <CardHeader><CardTitle>Symbol Analysis</CardTitle></CardHeader>
        <form onSubmit={runAnalysis} className="flex flex-col sm:flex-row gap-3 sm:items-end max-w-2xl">
          <div className="w-40">
            <Select
              label="Market"
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              options={[
                { value: "stock", label: "Stocks" },
                { value: "crypto", label: "Crypto" },
                { value: "forex", label: "Forex" },
                { value: "commodity", label: "Commodity" },
              ]}
            />
          </div>
          <Input
            label="Symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder={market === "crypto" ? "ETH/USD" : "AAPL"}
            required
          />
          <Button type="submit" disabled={loading}>
            {loading ? "Analyzing..." : "Analyze"}
          </Button>
        </form>

        {analysis?.regime && (
          <div className="mt-6 space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-lg font-semibold">{analysis.symbol}</span>
              <Badge variant={REGIME_VARIANT[analysis.regime.regime] ?? "gray"}>
                {analysis.regime.description}
              </Badge>
              <Badge variant={MOMENTUM_VARIANT[analysis.momentum?.overall ?? "neutral"] ?? "gray"}>
                momentum: {(analysis.momentum?.overall ?? "neutral").replace("_", " ")}
              </Badge>
              {analysis.current_price != null && (
                <span className="text-sm font-mono text-text-secondary">
                  ${analysis.current_price.toLocaleString()}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                <p className="text-sm font-medium text-text-secondary">Momentum (daily bars)</p>
                {[
                  { label: "Short term (5)", v: analysis.momentum?.short_term_pct ?? 0 },
                  { label: "Medium term (20)", v: analysis.momentum?.medium_term_pct ?? 0 },
                  { label: "Long term (50)", v: analysis.momentum?.long_term_pct ?? 0 },
                  { label: "Acceleration", v: analysis.momentum?.acceleration_pct ?? 0 },
                ].map((row) => (
                  <div key={row.label}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-muted">{row.label}</span>
                      <span className={clsx("font-mono", row.v >= 0 ? "text-green" : "text-red")}>
                        {row.v >= 0 ? "+" : ""}{row.v.toFixed(2)}%
                      </span>
                    </div>
                    <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden flex justify-center">
                      <div
                        className={clsx("h-full", row.v >= 0 ? "bg-green" : "bg-red")}
                        style={{
                          width: `${Math.min(Math.abs(row.v), 20) / 40 * 100}%`,
                          marginLeft: row.v >= 0 ? "50%" : undefined,
                          marginRight: row.v < 0 ? "50%" : undefined,
                        }}
                      />
                    </div>
                  </div>
                ))}
                <p className="text-xs text-text-muted">
                  Volatility: {analysis.volatility?.daily_pct}% daily / {analysis.volatility?.annualized_pct}% annualized · {analysis.bars_used} bars
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <p className="text-sm font-medium text-text-secondary">Trade Confidence</p>
                  <span className="text-2xl font-bold font-mono">
                    {((analysis.confidence?.score ?? 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full h-3 bg-bg-tertiary rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      "h-full rounded-full transition-all",
                      (analysis.confidence?.score ?? 0) >= 0.7 ? "bg-green"
                        : (analysis.confidence?.score ?? 0) >= 0.5 ? "bg-yellow" : "bg-red"
                    )}
                    style={{ width: `${(analysis.confidence?.score ?? 0) * 100}%` }}
                  />
                </div>
                <p className="text-sm text-text-secondary">{analysis.confidence?.recommendation}</p>
                <div className="space-y-1.5 border-t border-border pt-3">
                  {Object.entries(analysis.confidence?.breakdown ?? {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-text-muted capitalize">{k}</span>
                      <span className="font-mono">{(v * 100).toFixed(0)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-text-muted border-t border-border pt-3">
                  {analysis.regime.recommendation}
                </p>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Models */}
      <Card>
        <CardHeader><CardTitle>Model Ensemble</CardTitle></CardHeader>
        <div className="space-y-3">
          {models.length === 0 && <p className="text-sm text-text-muted">Loading models...</p>}
          {models.map((m) => (
            <div key={m.key} className="p-4 bg-bg-tertiary rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-sm">{m.name}</span>
                <Badge variant="purple">{m.kind}</Badge>
              </div>
              <p className="text-xs text-text-muted">{m.description}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
