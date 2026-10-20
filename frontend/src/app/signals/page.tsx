"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSignalsFeed } from "@/lib/signalsFeed";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { SignalPulse } from "@/components/ui/SignalPulse";
import { Stagger, StaggerItem } from "@/components/motion/Reveal";
import { RichText } from "@/components/learn/RichText";
import { tierLabel } from "@/lib/plans";
import type { AccuracyStats, CalendarEventContext, Signal } from "@/lib/types";

const MARKETS = ["all", "stock", "forex", "crypto", "commodity"] as const;
const STATUSES = ["active", "expired", "all"] as const;
const CATEGORIES = ["all", "meme", "hot", "major", "alt"] as const;

function categoryVariant(cat: string): "green" | "yellow" | "purple" | "blue" | "gray" {
  if (cat === "meme") return "purple";
  if (cat === "hot") return "yellow";
  if (cat === "major") return "blue";
  if (cat === "alt") return "gray";
  return "gray";
}

function outcomeVariant(outcome: string): "green" | "red" | "gray" | "yellow" {
  if (outcome === "tp") return "green";
  if (outcome === "sl") return "red";
  if (outcome === "expired") return "gray";
  return "yellow";
}

function rLabel(r: number): string {
  return `${r >= 0 ? "+" : ""}${r.toFixed(2)}R`;
}

function marketVariant(m: string): "blue" | "green" | "purple" | "yellow" {
  return m === "stock" ? "blue" : m === "forex" ? "green" : m === "commodity" ? "yellow" : "purple";
}

function eventCtx(s: Signal): CalendarEventContext | undefined {
  const ctx = s.indicators?.event_context;
  return ctx && typeof ctx === "object" ? (ctx as CalendarEventContext) : undefined;
}

function eventLabel(ctx: CalendarEventContext): string {
  const ev = ctx.events[0];
  if (!ev) return "Event soon";
  const mins = ev.minutes_away != null ? ` (${Math.round(ev.minutes_away)}m)` : "";
  return `Event soon: ${ev.name}${mins}`;
}

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

function SignalCardSkeleton() {
  return (
    <Card className="animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="space-y-2">
          <div className="h-4 w-24 rounded bg-bg-tertiary" />
          <div className="h-3 w-16 rounded bg-bg-tertiary" />
        </div>
        <div className="h-5 w-14 rounded bg-bg-tertiary" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-2.5 w-10 mx-auto rounded bg-bg-tertiary" />
            <div className="h-3.5 w-16 mx-auto rounded bg-bg-tertiary" />
          </div>
        ))}
      </div>
      <div className="mt-3 h-2.5 w-32 rounded bg-bg-tertiary" />
    </Card>
  );
}

export default function SignalsPage() {
  const { token, user } = useAuth();
  const { live, incoming } = useSignalsFeed();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [accuracy, setAccuracy] = useState<AccuracyStats | null>(null);
  const [market, setMarket] = useState<(typeof MARKETS)[number]>("all");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("active");
  const [cat, setCat] = useState<(typeof CATEGORIES)[number]>("all");
  const [selected, setSelected] = useState<Signal | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string>("");
  const [explain, setExplain] = useState<string>("");
  const [explainBusy, setExplainBusy] = useState(false);
  const seenRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    api<Signal[]>("/api/signals/?limit=100", { token })
      .then(setSignals)
      .catch(() => {})
      .finally(() => setLoading(false));
    api<AccuracyStats>("/api/signals/accuracy", { token })
      .then(setAccuracy)
      .catch(() => {});
  }, [token]);

  // Merge signals pushed by the app-wide SSE feed (see SignalsFeedProvider).
  useEffect(() => {
    if (incoming.length === 0) return;
    const fresh = incoming.filter((s) => !seenRef.current.has(s.id));
    if (fresh.length === 0) return;
    fresh.forEach((s) => seenRef.current.add(s.id));
    setSignals((prev) => {
      const ids = new Set(prev.map((p) => p.id));
      const add = fresh.filter((s) => !ids.has(s.id));
      return add.length ? [...add, ...prev] : prev;
    });
    const s = fresh[0];
    setToast(`New ${s.market} signal: ${s.symbol} ${s.direction.toUpperCase()}`);
    setTimeout(() => setToast(""), 5000);
  }, [incoming]);

  const openDetail = useCallback(
    async (s: Signal) => {
      setSelected(s);
      setExplain("");
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

  const askInstructor = useCallback(async () => {
    if (!token || !selected) return;
    setExplainBusy(true);
    try {
      const r = await api<{ reply: string }>("/api/learn/explain-signal", {
        method: "POST",
        token,
        body: { signal_id: selected.id },
      });
      setExplain(r.reply);
    } catch {
      setExplain("Couldn't reach the AI Instructor — please try again.");
    } finally {
      setExplainBusy(false);
    }
  }, [token, selected]);

  const filtered = useMemo(() => {
    const seen = new Set<string>();
    return signals.filter((s) => {
      if (seen.has(s.id)) return false;
      seen.add(s.id);
      return (
        (market === "all" || s.market === market) &&
        (status === "all" || s.status === status) &&
        (cat === "all" || (s.category ?? "").toLowerCase() === cat)
      );
    });
  }, [signals, market, status, cat]);

  const catCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of signals) {
      const c = (s.category ?? "").toLowerCase();
      if (c) counts[c] = (counts[c] ?? 0) + 1;
    }
    return counts;
  }, [signals]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">AI Signals</h1>
          {live && <SignalPulse size={26} rings={2} />}
        </div>
        <Badge variant={live ? "green" : "gray"} dot>
          {live ? "LIVE FEED" : "FEED OFFLINE"}
        </Badge>
      </div>

      {toast && (
        <Card className="border-green/40">
          <p className="text-sm text-green">{toast}</p>
        </Card>
      )}

      {(user?.tier || "free").toLowerCase() !== "vip" && (
        <Card className="border-green/30 bg-green/5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-text-secondary">
              You&apos;re on the <span className="font-medium text-text-primary">{tierLabel(user?.tier)}</span> plan —
              more signals (stocks, commodities, crypto &amp; memecoins) are locked.
              {(user?.tier || "free").toLowerCase() === "free"
                ? " Your feed is 5 minutes behind real time."
                : " Your feed is 1 minute behind real time."}
            </p>
            <Link href="/vip">
              <Button size="sm">See plans & upgrade</Button>
            </Link>
          </div>
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
        <span className="w-px h-5 bg-border mx-1" />
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCat(c)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              cat === c ? "bg-purple text-white" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
            }`}
          >
            {c === "all" ? "ALL TYPES" : `${c.toUpperCase()}${catCounts[c] ? ` ${catCounts[c]}` : ""}`}
          </button>
        ))}
        <span className="ml-auto text-xs text-text-muted">{filtered.length} signals</span>
      </div>

      {loading && signals.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SignalCardSkeleton key={i} />)}
        </div>
      ) : (
      <Stagger className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.length === 0 && (
          <Card><p className="text-sm text-text-muted">No signals yet. Run an engine scan or wait for the live feed.</p></Card>
        )}
        {filtered.map((s) => {
          const eff = s.effective_confidence ?? s.confidence;
          const ctx = eventCtx(s);
          return (
            <StaggerItem key={s.id}>
            <Card className={`hover:border-border-light transition-colors ${s.locked ? "" : "cursor-pointer"}`} >
              <div onClick={s.locked ? undefined : () => openDetail(s)}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-base">{s.symbol}</h3>
                      <Badge variant={marketVariant(s.market)}>
                        {s.market}
                      </Badge>
                      {s.category && s.category !== s.market && (
                        <Badge variant={categoryVariant(s.category)}>{s.category}</Badge>
                      )}
                    </div>
                    <p className="text-xs text-text-muted mt-1">{s.strategy}</p>
                    {(s.outcome || s.data_source === "simulated") && (
                      <div className="flex items-center gap-2 mt-2">
                        {s.outcome && (
                          <Badge variant={outcomeVariant(s.outcome)}>{s.outcome.toUpperCase()}</Badge>
                        )}
                        {s.r_multiple != null && (
                          <span className={`text-xs font-mono ${s.r_multiple >= 0 ? "text-green" : "text-red-400"}`}>
                            {rLabel(s.r_multiple)}
                          </span>
                        )}
                        {s.data_source === "simulated" && (
                          <Badge variant="yellow">SIMULATED</Badge>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {s.locked && <Badge variant="purple">LOCKED</Badge>}
                    <Badge variant={s.direction === "buy" ? "green" : "red"} dot>
                      {s.direction.toUpperCase()}
                    </Badge>
                  </div>
                </div>

                <div className="relative">
                  <div className={`grid grid-cols-3 gap-3 text-center ${s.locked ? "blur-[6px] select-none" : ""}`}>
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
                  {s.locked && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5">
                      <p className="text-[11px] font-semibold text-text-secondary">
                        Upgrade to unlock entry, SL &amp; TP
                      </p>
                      <Link href="/vip" onClick={(e) => e.stopPropagation()}>
                        <Button size="sm" variant="secondary">See plans</Button>
                      </Link>
                    </div>
                  )}
                </div>

                {ctx && (
                  <div className="mt-3">
                    <Badge variant="yellow">{eventLabel(ctx)}</Badge>
                  </div>
                )}

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
                {!s.locked && (
                  <div className="mt-3 flex gap-2">
                    <Link
                      href={`/trading?mode=demo&symbol=${encodeURIComponent(s.symbol)}&side=${s.direction}&entry=${s.entry_price}&sl=${s.stop_loss ?? ""}&tp=${s.take_profit ?? ""}&market=${s.market}`}
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center justify-center rounded-lg border border-blue/60 px-3 py-1.5 text-xs font-medium text-blue hover:bg-blue/10 transition-colors"
                    >
                      Test in Demo
                    </Link>
                  </div>
                )}
              </div>
            </Card>
            </StaggerItem>
          );
        })}
      </Stagger>
      )}

      {accuracy?.outcomes && accuracy.outcomes.resolved > 0 && (
        <Card>
          <CardHeader><CardTitle>Signal Outcomes</CardTitle></CardHeader>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-[10px] text-text-muted uppercase">Hit Rate</p>
              <p className={`text-xl font-mono font-semibold ${accuracy.outcomes.win_rate >= 50 ? "text-green" : "text-red-400"}`}>
                {accuracy.outcomes.win_rate}%
              </p>
            </div>
            <div>
              <p className="text-[10px] text-text-muted uppercase">Resolved</p>
              <p className="text-xl font-mono font-semibold">{accuracy.outcomes.resolved}</p>
            </div>
            <div>
              <p className="text-[10px] text-text-muted uppercase">Avg R</p>
              <p className={`text-xl font-mono font-semibold ${accuracy.outcomes.avg_r >= 0 ? "text-green" : "text-red-400"}`}>
                {accuracy.outcomes.avg_r >= 0 ? "+" : ""}{accuracy.outcomes.avg_r.toFixed(2)}R
              </p>
            </div>
            <div>
              <p className="text-[10px] text-text-muted uppercase">TP / SL</p>
              <p className="text-xl font-mono font-semibold">
                <span className="text-green">{accuracy.outcomes.by_outcome.tp ?? 0}</span>
                <span className="text-text-muted"> / </span>
                <span className="text-red-400">{accuracy.outcomes.by_outcome.sl ?? 0}</span>
              </p>
            </div>
          </div>
          {accuracy.outcomes.by_market.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[420px]">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-xs text-text-muted py-2">Market</th>
                    <th className="text-right text-xs text-text-muted py-2">Resolved</th>
                    <th className="text-right text-xs text-text-muted py-2">Wins</th>
                    <th className="text-right text-xs text-text-muted py-2">Hit Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {accuracy.outcomes.by_market.map((m) => (
                    <tr key={m.market} className="border-b border-border/50 last:border-0">
                      <td className="py-2.5 font-medium capitalize">{m.market}</td>
                      <td className="py-2.5 text-right font-mono">{m.resolved}</td>
                      <td className="py-2.5 text-right font-mono">{m.wins}</td>
                      <td className="py-2.5 text-right font-mono">
                        <span className={m.win_rate >= 50 ? "text-green" : "text-red-400"}>{m.win_rate}%</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(accuracy.outcomes.live > 0 || accuracy.outcomes.simulated > 0 || accuracy.outcomes.unknown > 0) && (
            <p className="text-xs text-text-muted mt-3">
              Data source across resolved signals: {accuracy.outcomes.live} live
              {accuracy.outcomes.simulated > 0 ? `, ${accuracy.outcomes.simulated} simulated (included for reference)` : ""}
              {accuracy.outcomes.unknown > 0 ? `, ${accuracy.outcomes.unknown} unclassified` : ""}.
            </p>
          )}
        </Card>
      )}

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
              <table className="w-full text-sm min-w-[600px]">
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
              <Badge variant={marketVariant(selected.market)}>
                {selected.market}
              </Badge>
              {selected.category && selected.category !== selected.market && (
                <Badge variant={categoryVariant(selected.category)}>{selected.category}</Badge>
              )}
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

            <Link
              href={`/charts?symbol=${encodeURIComponent(selected.symbol)}&market=${selected.market}&entry=${selected.entry_price}&sl=${selected.stop_loss ?? ""}&tp=${selected.take_profit ?? ""}&side=${selected.direction}`}
              className="inline-flex w-full items-center justify-center rounded-lg border border-border bg-bg-tertiary px-4 py-2 text-sm font-medium text-text-primary hover:bg-hover transition-colors"
            >
              View chart with entry / stop / target
            </Link>
            {!selected.locked && (
              <Link
                href={`/trading?mode=demo&symbol=${encodeURIComponent(selected.symbol)}&side=${selected.direction}&entry=${selected.entry_price}&sl=${selected.stop_loss ?? ""}&tp=${selected.take_profit ?? ""}&market=${selected.market}`}
                className="inline-flex w-full items-center justify-center rounded-lg border border-blue/60 bg-blue/10 px-4 py-2 text-sm font-medium text-blue hover:bg-blue/20 transition-colors"
              >
                Test in Demo
              </Link>
            )}

            {eventCtx(selected) && (
              <div className="bg-yellow-dim text-yellow text-xs rounded-lg p-3">
                {eventLabel(eventCtx(selected) as CalendarEventContext)} — this signal may be affected by
                a scheduled event.
              </div>
            )}

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
                  {Object.entries(selected.indicators)
                    .filter(([k]) => k !== "event_context")
                    .slice(0, 12)
                    .map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2">
                      <span className="text-text-muted">{k}</span>
                      <span>
                        {k === "sentiment" && v && typeof v === "object"
                          ? (() => {
                              const s = v as { available?: boolean; modifier?: number; tag?: string | null };
                              if (!s.available) return "n/a";
                              const m = s.modifier ?? 0;
                              const adj = m >= 0 ? `+${(m * 100).toFixed(1)}%` : `${(m * 100).toFixed(1)}%`;
                              return s.tag ? `${s.tag} ${adj}` : adj;
                            })()
                          : typeof v === "number"
                          ? v.toFixed(3)
                          : v && typeof v === "object"
                            ? Object.values(v as Record<string, number>)
                                .map((x) => (typeof x === "number" ? x.toFixed(3) : String(x)))
                                .join(" / ")
                            : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="border-t border-border pt-4">
              {explain ? (
                <div className="text-sm bg-bg-tertiary rounded-lg p-3">
                  <p className="text-xs text-green uppercase mb-2">AI Instructor</p>
                  <RichText text={explain} />
                </div>
              ) : (
                <Button variant="secondary" size="sm" onClick={askInstructor} disabled={explainBusy} className="w-full">
                  {explainBusy ? "Thinking…" : "Ask the AI Instructor to explain this signal"}
                </Button>
              )}
            </div>

            <p className="text-xs text-text-muted">
              Generated {new Date(selected.created_at).toLocaleString()}
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
