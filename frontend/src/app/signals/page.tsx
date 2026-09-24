"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import type { AccuracyStats, Signal } from "@/lib/types";

const MARKETS = ["all", "stock", "forex", "crypto"] as const;
const STATUSES = ["active", "expired", "all"] as const;

function fmt(v: number | null | undefined): string {
  if (v == null) return "—";
  return v >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v.toFixed(4);
}

function ageLabel(hours: number | null | undefined): string {
  if (hours == null) return "";
  if (hours < 1) return `${Math.round(hours * 60)}m ago`;
  if (hours < 24) return `${Math.floor(hours)}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function confColor(c: number): string {
  return c >= 0.8 ? "#00D68F" : c >= 0.6 ? "#FFBE0B" : "#FF4757";
}

export default function SignalsPage() {
  const { token, user } = useAuth();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [accuracy, setAccuracy] = useState<AccuracyStats | null>(null);
  const [market, setMarket] = useState<(typeof MARKETS)[number]>("all");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("active");
  const [selected, setSelected] = useState<Signal | null>(null);
  const [live, setLive] = useState(false);
  const [toast, setToast] = useState<string>("");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!token) return;
    api<Signal[]>("/api/signals/?limit=100", { token })
      .then(setSignals)
      .catch(() => {});
    api<AccuracyStats>("/api/signals/accuracy", { token })
      .then(setAccuracy)
      .catch(() => {});
  }, [token]);

  // Live SSE feed — new signals arrive pushed, gated server-side by tier
  useEffect(() => {
    if (!token || !user) return;
    const url = `${API_BASE}/api/signals/feed?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("signal", (ev) => {
      try {
        const s: Signal = JSON.parse((ev as MessageEvent).data);
        setSignals((prev) => (prev.some((p) => p.id === s.id) ? prev : [s, ...prev]));
        setToast(`New ${s.market} signal: ${s.symbol} ${s.direction.toUpperCase()}`);
        setTimeout(() => setToast(""), 5000);
      } catch {}
    });
    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);

    return () => {
      es.close();
      esRef.current = null;
      setLive(false);
    };
  }, [token, user]);

  const openDetail = useCallback(
    async (s: Signal) => {
      setSelected(s);
      if (!token) return;
      try {
        const fresh = await api<Signal>(`/api/signals/${s.id}`, { token });
        setSelected(fresh);
      } catch {
        /* keep the list version */
      }
    },
    [token]
  );

  const filtered = signals.filter(
    (s) =>
      (market === "all" || s.market === market) &&
      (status === "all" || s.status === status)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">AI Signals</h1>
        <Badge variant={live ? "green" : "gray"} dot>
          {live ? "LIVE FEED" : "FEED OFFLINE"}
        </Badge>
      </div>

      {toast && (
        <Card className="border-green/40">
          <p className="text-sm text-green">{toast}</p>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {MARKETS.map((m) => (
          <button
            key={m}
            onClick={() => setMarket(m)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              market === m ? "bg-green text-black" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
            }`}
          >
            {m.toUpperCase()}
          </button>
        ))}
        <span className="w-px h-5 bg-border mx-1" />
        {STATUSES.map((st) => (
          <button
            key={st}
            onClick={() => setStatus(st)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              status === st ? "bg-blue text-white" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
            }`}
          >
            {st.toUpperCase()}
          </button>
        ))}
        <span className="ml-auto text-xs text-text-muted">{filtered.length} signals</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.length === 0 && (
          <Card><p className="text-sm text-text-muted">No signals yet. Run an engine scan or wait for the live feed.</p></Card>
        )}
        {filtered.map((s) => {
          const eff = s.effective_confidence ?? s.confidence;
          return (
            <Card key={s.id} className="hover:border-border-light transition-colors cursor-pointer" >
              <div onClick={() => openDetail(s)}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-base">{s.symbol}</h3>
                      <Badge variant={s.market === "stock" ? "blue" : s.market === "forex" ? "green" : "purple"}>
                        {s.market}
                      </Badge>
                    </div>
                    <p className="text-xs text-text-muted mt-1">{s.strategy}</p>
                  </div>
                  <Badge variant={s.direction === "buy" ? "green" : "red"} dot>
                    {s.direction.toUpperCase()}
                  </Badge>
                </div>

                <div className="grid grid-cols-3 gap-3 text-center">
                  <div>
                    <p className="text-[10px] text-text-muted uppercase">Entry</p>
                    <p className="text-sm font-mono font-medium mt-0.5">{fmt(s.entry_price)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted uppercase">Stop Loss</p>
                    <p className="text-sm font-mono font-medium mt-0.5 text-red-400">{fmt(s.stop_loss)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-text-muted uppercase">Take Profit</p>
                    <p className="text-sm font-mono font-medium mt-0.5 text-green">{fmt(s.take_profit)}</p>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-text-muted">Confidence</span>
                    <div className="w-20 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${eff * 100}%`, backgroundColor: confColor(eff) }}
                      />
                    </div>
                    <span className="text-xs font-mono">{(eff * 100).toFixed(0)}%</span>
                    {s.age_hours != null && s.age_hours > 1 && (
                      <span className="text-[10px] text-text-muted" title="decayed with signal age">
                        ↓{ageLabel(s.age_hours)}
                      </span>
                    )}
                  </div>
                  <Badge variant={s.tier_required === "free" ? "gray" : s.tier_required === "premium" ? "yellow" : "purple"}>
                    {s.tier_required}
                  </Badge>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader><CardTitle>Historical Signal Accuracy</CardTitle></CardHeader>
        {!accuracy || accuracy.strategies.length === 0 ? (
          <p className="text-sm text-text-muted">No closed trades yet — accuracy appears as strategies complete trades.</p>
        ) : (
          <>
            <p className="text-sm text-text-secondary mb-4">
              Overall win rate across {accuracy.overall.closed_trades} closed trades:{" "}
              <span className="font-mono font-semibold text-green">{accuracy.overall.win_rate}%</span>
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-xs text-text-muted py-2">Strategy</th>
                    <th className="text-left text-xs text-text-muted py-2">Markets</th>
                    <th className="text-right text-xs text-text-muted py-2">Trades</th>
                    <th className="text-right text-xs text-text-muted py-2">Win Rate</th>
                    <th className="text-right text-xs text-text-muted py-2">Total P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {accuracy.strategies.map((st) => (
                    <tr key={st.strategy} className="border-b border-border/50 last:border-0">
                      <td className="py-2.5 font-medium">{st.strategy}</td>
                      <td className="py-2.5 text-text-secondary">{st.markets.join(", ")}</td>
                      <td className="py-2.5 text-right font-mono">{st.closed_trades}</td>
                      <td className="py-2.5 text-right font-mono">
                        <span className={st.win_rate >= 50 ? "text-green" : "text-red-400"}>{st.win_rate}%</span>
                      </td>
                      <td className={`py-2.5 text-right font-mono ${st.total_pnl >= 0 ? "text-green" : "text-red-400"}`}>
                        {st.total_pnl >= 0 ? "+" : ""}${st.total_pnl.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected ? `${selected.symbol} — Signal Details` : ""}>
        {selected && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge variant={selected.direction === "buy" ? "green" : "red"} dot>
                {selected.direction.toUpperCase()}
              </Badge>
              <Badge variant={selected.market === "stock" ? "blue" : selected.market === "forex" ? "green" : "purple"}>
                {selected.market}
              </Badge>
              <Badge variant={selected.status === "active" ? "green" : "gray"}>{selected.status}</Badge>
              <Badge variant={selected.tier_required === "free" ? "gray" : selected.tier_required === "premium" ? "yellow" : "purple"}>
                {selected.tier_required}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-bg-tertiary rounded-lg p-3">
                <p className="text-xs text-text-muted">Entry Price</p>
                <p className="font-mono font-medium mt-1">{fmt(selected.entry_price)}</p>
              </div>
              <div className="bg-bg-tertiary rounded-lg p-3">
                <p className="text-xs text-text-muted">Strategy</p>
                <p className="font-medium mt-1">{selected.strategy ?? "—"}</p>
              </div>
              <div className="bg-bg-tertiary rounded-lg p-3">
                <p className="text-xs text-text-muted">Stop Loss</p>
                <p className="font-mono font-medium mt-1 text-red-400">{fmt(selected.stop_loss)}</p>
              </div>
              <div className="bg-bg-tertiary rounded-lg p-3">
                <p className="text-xs text-text-muted">Take Profit</p>
                <p className="font-mono font-medium mt-1 text-green">{fmt(selected.take_profit)}</p>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-text-muted">Original confidence</span>
                <span className="font-mono">{(selected.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-text-muted">
                  Effective now {selected.age_hours != null && `(${ageLabel(selected.age_hours)})`}
                </span>
                <span className="font-mono" style={{ color: confColor(selected.effective_confidence ?? selected.confidence) }}>
                  {((selected.effective_confidence ?? selected.confidence) * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-xs text-text-muted mt-2">Confidence decays with a 12-hour half-life from generation time.</p>
            </div>

            {selected.indicators && Object.keys(selected.indicators).length > 0 && (
              <div>
                <p className="text-xs text-text-muted uppercase mb-2">Indicators at generation</p>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-bg-tertiary rounded-lg p-3">
                  {Object.entries(selected.indicators).slice(0, 10).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2">
                      <span className="text-text-muted">{k}</span>
                      <span>{typeof v === "number" ? v.toFixed(3) : String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="text-xs text-text-muted">
              Generated {new Date(selected.created_at).toLocaleString()}
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
