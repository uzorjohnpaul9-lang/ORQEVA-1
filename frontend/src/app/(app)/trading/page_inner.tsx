"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const MARKETS = [
  { value: "forex", label: "Forex" },
  { value: "crypto", label: "Crypto" },
  { value: "stock", label: "Stock" },
];

export default function TradingPage() {
  const { token } = useAuth();
  const params = useSearchParams();
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // order form state
  const [symbol, setSymbol] = useState("EUR/USD");
  const [market, setMarket] = useState("forex");
  const [side, setSide] = useState("buy");
  const [quantity, setQuantity] = useState("10000");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const route = mode === "live" ? "live" : "paper";
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const qMode = params.get("mode");
    const qSymbol = params.get("symbol")?.trim();
    const qSide = params.get("side");
    const qSl = params.get("sl");
    const qTp = params.get("tp");
    const qMarket = params.get("market");
    if (qMode === "demo" || qMode === "live") setMode(qMode);
    if (qSymbol) setSymbol(qSymbol);
    if (qSide === "buy" || qSide === "sell") setSide(qSide);
    if (qMarket === "forex" || qMarket === "crypto" || qMarket === "stock" || qMarket === "commodity") setMarket(qMarket);
    if (qSl) setStopLoss(qSl);
    if (qTp) setTakeProfit(qTp);
  }, [params]);

  const [connections, setConnections] = useState<{ exchange: string; is_active: boolean }[]>([]);
  const [adapterMarkets, setAdapterMarkets] = useState<Record<string, string[]>>({});
  useEffect(() => {
    if (!token) return;
    api<{ exchange: string; is_active: boolean }[]>("/api/exchanges", { token })
      .then(setConnections)
      .catch(() => {});
    api<{ name: string; markets: string[] }[]>("/api/exchanges/meta", { token })
      .then((list) => setAdapterMarkets(Object.fromEntries(list.map((a) => [a.name, a.markets ?? []]))))
      .catch(() => {});
  }, [token]);

  // Any active connection whose adapter serves this market can route the order,
  // so the venue list stays in sync with the backend registry automatically.
  const liveVenue = connections.find(
    (c) => c.is_active && (adapterMarkets[c.exchange] ?? []).includes(market),
  );

  async function placeOrder(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    const idemKey =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `k${Date.now()}${Math.random().toString(36).slice(2)}`;
    try {
      const res = await api<{
        status: string; symbol: string; side: string;
        entry_price: number; venue: string; broker_order_id: string | null;
      }>("/api/trading/orders", {
        method: "POST",
        token,
        body: JSON.stringify({
          symbol, market, side, quantity: Number(quantity), route,
          idempotency_key: idemKey,
          ...(stopLoss ? { stop_loss: Number(stopLoss) } : {}),
          ...(takeProfit ? { take_profit: Number(takeProfit) } : {}),
        }),
      });
      const where = res.venue && res.venue !== "paper" ? ` via ${res.venue}` : "";
      setNotice(`Order filled: ${res.side.toUpperCase()} ${res.symbol} @ ${res.entry_price}${where}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function resetDemo() {
    if (!token || !window.confirm("Clear all demo trades and restore the starting balance?")) return;
    setResetting(true);
    setError(null);
    try {
      const res = await api<{ deleted: number; starting_balance: number }>("/api/trading/demo/reset", {
        method: "POST",
        token,
        body: "{}",
      });
      setNotice(`Demo reset: cleared ${res.deleted} trade(s). Balance $${res.starting_balance.toLocaleString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo reset failed");
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Trading</h1>
          <p className="text-sm text-text-secondary mt-1">
            {mode === "demo"
              ? "Practice with a virtual balance - no real money at risk"
              : "Place live orders at your connected broker"}
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-bg-tertiary p-1">
          {(["demo", "live"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === m ? "bg-green text-bg" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {m === "demo" ? "Demo" : "Live"}
            </button>
          ))}
        </div>
      </div>

      {mode === "demo" ? (
        <Card className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Badge variant="purple">DEMO</Badge>
            <p className="text-sm text-text-secondary">
              You are trading a virtual account. Connect a broker to trade live.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={resetDemo} disabled={resetting}>
              {resetting ? "Resetting..." : "Reset Demo"}
            </Button>
            <a
              href="/exchanges"
              className="inline-flex items-center rounded-lg border border-green px-3 py-2 text-sm font-medium text-green hover:bg-green hover:text-bg transition-colors"
            >
              Go Live
            </a>
          </div>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-text-secondary">
            Live orders execute at your connected broker. Demo trades stay separate and are not
            affected by live activity.
          </p>
        </Card>
      )}

      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}
      {(params.get("mode") === "demo" || params.get("symbol")) && (
        <Card className="border-blue/40 bg-blue/5">
          <p className="text-sm text-blue">
            Testing signal in Demo — values pre-filled from signal
          </p>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>New Order</CardTitle>
          </CardHeader>
          <form onSubmit={placeOrder} className="space-y-4">
            <Input label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} required />
            <Select label="Market" value={market} options={MARKETS} onChange={(e) => setMarket(e.target.value)} />
            <Select
              label="Side"
              value={side}
              options={[
                { value: "buy", label: "Buy (Long)" },
                { value: "sell", label: "Sell (Short)" },
              ]}
              onChange={(e) => setSide(e.target.value)}
            />
            <Input
              label="Quantity"
              type="number"
              min="0"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
            <div className="flex items-center justify-between rounded-lg border border-border bg-bg-tertiary px-3 py-2 text-sm">
              <span className="text-text-muted">Account</span>
              <Badge variant={mode === "demo" ? "purple" : "green"}>
                {mode === "demo" ? "DEMO" : "LIVE"}
              </Badge>
            </div>
            {route === "live" && (
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Stop Loss"
                  type="number"
                  min="0"
                  step="any"
                  placeholder="Optional"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                />
                <Input
                  label="Take Profit"
                  type="number"
                  min="0"
                  step="any"
                  placeholder="Optional"
                  value={takeProfit}
                  onChange={(e) => setTakeProfit(e.target.value)}
                />
              </div>
            )}
            {route === "live" && (
              <p className={`text-xs ${liveVenue ? "text-green" : "text-red"}`}>
                {liveVenue
                  ? `Will execute via your ${liveVenue.exchange} connection`
                  : `No active broker connection for ${market}. Connect one on the Exchanges page.`}
              </p>
            )}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Placing..." : `Place ${side.toUpperCase()} Order`}
            </Button>
            <p className="text-xs text-text-muted">
              {route === "live"
                ? "Real order at your connected broker. Risk checks still apply."
                : "Executes at live market price on paper exchange."}
            </p>
          </form>
        </Card>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Execution Context</CardTitle>
            </CardHeader>
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-bg-tertiary p-3">
                  <p className="text-xs text-text-muted">Symbol</p>
                  <p className="mt-1 font-medium">{symbol || "-"}</p>
                </div>
                <div className="rounded-lg bg-bg-tertiary p-3">
                  <p className="text-xs text-text-muted">Market</p>
                  <p className="mt-1 font-medium capitalize">{market}</p>
                </div>
                <div className="rounded-lg bg-bg-tertiary p-3">
                  <p className="text-xs text-text-muted">Route</p>
                  <Badge variant={route === "live" ? "green" : "purple"}>{route === "live" ? "LIVE" : "PAPER"}</Badge>
                </div>
                <div className="rounded-lg bg-bg-tertiary p-3">
                  <p className="text-xs text-text-muted">Side</p>
                  <Badge variant={side === "buy" ? "green" : "red"}>{side.toUpperCase()}</Badge>
                </div>
              </div>

              <p className="text-text-secondary">
                Open positions, closed trades and performance live in Portfolio. Risk limits apply to every order.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Link
                  href={`/market/charts?symbol=${encodeURIComponent(symbol || "")}&market=${market}&side=${side}`}
                  className="inline-flex items-center justify-center rounded-lg border border-border bg-bg-tertiary px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover"
                >
                  Open chart
                </Link>
                <Link
                  href="/portfolio/positions"
                  className="inline-flex items-center justify-center rounded-lg border border-border bg-bg-tertiary px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover"
                >
                  View positions
                </Link>
                <Link
                  href="/portfolio/history"
                  className="inline-flex items-center justify-center rounded-lg border border-border bg-bg-tertiary px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover"
                >
                  Trade history
                </Link>
                <Link
                  href="/risk"
                  className="inline-flex items-center justify-center rounded-lg border border-border bg-bg-tertiary px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover"
                >
                  Risk settings
                </Link>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
