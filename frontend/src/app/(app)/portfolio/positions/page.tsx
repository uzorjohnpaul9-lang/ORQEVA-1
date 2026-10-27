"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { TradePanel } from "@/components/trade/TradePanel";
import { StatCard } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Position } from "@/lib/types";

export default function PositionsPage() {
  const { token } = useAuth();
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setPositions(await api<Position[]>("/api/portfolio/positions", { token }));
      setError(null);
    } catch {
      setError("Could not load positions");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function closePosition(id: string) {
    if (!token) return;
    setClosingId(id);
    setError(null);
    try {
      await api(`/api/trading/close/${id}`, { method: "POST", token, body: "{}" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not close position");
    } finally {
      setClosingId(null);
    }
  }

  const invested = positions.reduce((sum, t) => sum + t.entry_price * t.quantity, 0);
  const unrealized = positions.reduce((sum, t) => sum + (t.unrealized_pnl ?? 0), 0);
  const unrealPct = invested > 0 ? `${unrealized >= 0 ? "+" : ""}${(unrealized / invested * 100).toFixed(2)}%` : undefined;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Positions</h1>
        <p className="text-sm text-text-secondary mt-1">{positions.length} positions open</p>
      </div>

      {error && <p className="text-sm text-red">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Open Positions" value={positions.length.toString()} />
        <StatCard label="Total Invested" value={`$${invested.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
        <StatCard
          label="Unrealized P&L"
          value={`${unrealized >= 0 ? "+" : ""}$${Math.abs(unrealized).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          change={unrealPct}
        />
      </div>

      {loading ? (
        <p className={clsx("text-sm text-text-muted")}>Loading positions...</p>
      ) : positions.length === 0 && !error ? (
        <p className="text-sm text-text-muted">No open positions.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {positions.map((t) => (
            <TradePanel
              key={t.id}
              trade={t}
              onClose={() => closePosition(t.id)}
              closing={closingId === t.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
