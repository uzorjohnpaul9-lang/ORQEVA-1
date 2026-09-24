"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DataTable } from "@/components/tables/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface TradeRow {
  id: string;
  symbol: string;
  market: string;
  side: string;
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  pnl: number | null;
  strategy: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
}

interface HistoryResponse {
  total: number;
  limit: number;
  offset: number;
  trades: TradeRow[];
  summary: { in_page: number; wins: number; losses: number; win_rate_pct: number; total_pnl: number };
}

const PAGE_SIZE = 25;

export default function HistoryPage() {
  const { token } = useAuth();
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);

  // filters
  const [market, setMarket] = useState("");
  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("");
  const [outcome, setOutcome] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const query = useMemo(() => {
    const p = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
    if (market) p.set("market", market);
    if (symbol.trim()) p.set("symbol", symbol.trim());
    if (strategy.trim()) p.set("strategy", strategy.trim());
    if (outcome) p.set("outcome", outcome);
    if (startDate) p.set("start", startDate);
    if (endDate) p.set("end", endDate);
    return p.toString();
  }, [market, symbol, strategy, outcome, startDate, endDate, page]);

  const refresh = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      setData(await api<HistoryResponse>(`/api/trading/history?${query}`, { token }));
      setError(null);
    } catch {
      setError("Could not load trade history");
    } finally {
      setLoading(false);
    }
  }, [token, query]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function resetFilters() {
    setMarket(""); setSymbol(""); setStrategy(""); setOutcome("");
    setStartDate(""); setEndDate(""); setPage(0);
  }

  const s = data?.summary;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Trading History</h1>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard label="Total Trades" value={data ? `${data.total}` : "-"} />
        <StatCard label="Total P&L" value={s ? `$${s.total_pnl.toLocaleString()}` : "-"} />
        <StatCard label="Win Rate" value={s ? `${s.win_rate_pct}%` : "-"} change={s ? `${s.wins}W / ${s.losses}L` : undefined} />
        <StatCard label="Showing" value={s ? `${s.in_page} of ${data?.total ?? 0}` : "-"} />
      </div>

      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
          <select
            value={market}
            onChange={(e) => { setMarket(e.target.value); setPage(0); }}
            className="bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary outline-none focus:border-green/50 transition-colors"
          >
            <option value="">All Markets</option>
            <option value="stock">Stocks</option>
            <option value="forex">Forex</option>
            <option value="crypto">Crypto</option>
            <option value="commodity">Commodity</option>
          </select>
          <select
            value={outcome}
            onChange={(e) => { setOutcome(e.target.value); setPage(0); }}
            className="bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary outline-none focus:border-green/50 transition-colors"
          >
            <option value="">All Outcomes</option>
            <option value="win">Wins</option>
            <option value="loss">Losses</option>
            <option value="open">Open</option>
          </select>
          <Input label="Symbol" value={symbol} onChange={(e) => { setSymbol(e.target.value); setPage(0); }} placeholder="e.g. AAPL" />
          <Input label="Strategy" value={strategy} onChange={(e) => { setStrategy(e.target.value); setPage(0); }} placeholder="e.g. manual" />
          <Input label="From" type="date" value={startDate} onChange={(e) => { setStartDate(e.target.value); setPage(0); }} />
          <Input label="To" type="date" value={endDate} onChange={(e) => { setEndDate(e.target.value); setPage(0); }} />
        </div>
        <div className="flex gap-2 mt-3">
          <Button variant="secondary" size="sm" onClick={resetFilters}>Reset Filters</Button>
        </div>
      </Card>

      {error && <p className="text-sm text-red">{error}</p>}

      <Card padding={false}>
        <DataTable
          columns={[
            { key: "symbol", header: "Symbol", render: (t: TradeRow) => <span className="font-medium">{t.symbol}</span> },
            { key: "market", header: "Market", render: (t: TradeRow) => <Badge variant={t.market === "stock" ? "blue" : t.market === "forex" ? "green" : "purple"}>{t.market}</Badge> },
            { key: "side", header: "Side", render: (t: TradeRow) => <Badge variant={t.side === "buy" ? "green" : "red"}>{t.side.toUpperCase()}</Badge> },
            { key: "qty", header: "Qty", render: (t: TradeRow) => <span className="font-mono">{t.quantity.toLocaleString()}</span> },
            { key: "entry", header: "Entry", render: (t: TradeRow) => <span className="font-mono">{t.entry_price.toLocaleString()}</span> },
            { key: "exit", header: "Exit", render: (t: TradeRow) => <span className="font-mono">{t.exit_price?.toLocaleString() || "-"}</span> },
            { key: "pnl", header: "P&L", render: (t: TradeRow) => (
              <span className={`font-mono font-bold ${(t.pnl || 0) >= 0 ? "text-green" : "text-red"}`}>
                {t.pnl !== null ? `${t.pnl >= 0 ? "+" : ""}$${Math.abs(t.pnl).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "-"}
              </span>
            )},
            { key: "strategy", header: "Strategy", render: (t: TradeRow) => <span className="text-text-secondary">{t.strategy}</span> },
            { key: "status", header: "Status", render: (t: TradeRow) => <Badge variant={t.status === "open" ? "yellow" : t.status === "closed" ? ((t.pnl || 0) >= 0 ? "green" : "red") : "gray"}>{t.status}</Badge> },
            { key: "opened", header: "Opened", render: (t: TradeRow) => <span className="text-xs text-text-muted">{new Date(t.opened_at).toLocaleDateString()}</span> },
          ]}
          data={data?.trades ?? []}
        />
        {!loading && data && data.trades.length === 0 && (
          <p className="text-sm text-text-muted py-8 text-center">No trades match these filters.</p>
        )}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
          <Button variant="secondary" size="sm" disabled={page === 0 || loading} onClick={() => setPage((p) => Math.max(p - 1, 0))}>
            Previous
          </Button>
          <span className="text-xs text-text-muted">Page {page + 1}</span>
          <Button
            variant="secondary" size="sm"
            disabled={loading || !data || (page + 1) * PAGE_SIZE >= data.total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </Card>
    </div>
  );
}
