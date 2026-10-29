"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Download, Info } from "lucide-react";
import {
  EMPTY_SNAPSHOT,
  TRACK_RECORD_CSV_URL,
  fetchTrackRecord,
  formatDate,
  formatPct,
  formatR,
  type TrackRecordSnapshot,
} from "@/lib/track-record";

function outcomeClass(outcome: string): string {
  if (outcome === "tp") return "text-green";
  if (outcome === "sl") return "text-red";
  if (outcome === "breakeven") return "text-yellow";
  return "text-text-muted";
}

export function TrackRecordLive({ full = false }: { full?: boolean }) {
  const [snapshot, setSnapshot] = useState<TrackRecordSnapshot | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    fetchTrackRecord(controller.signal)
      .then((data) => {
        if (active) setSnapshot(data);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const s = snapshot ?? EMPTY_SNAPSHOT;
  const loading = snapshot === null && !failed;
  const rows = s.recent.slice(0, full ? 50 : 8);
  const hasRows = rows.length > 0;

  const statusText = loading
    ? "Loading the public ledger…"
    : failed
      ? "Live ledger feed is temporarily unavailable. The CSV endpoint remains the source of truth."
      : s.status === "collecting"
        ? `Collecting live track record — ${s.sample.resolved} of ${s.sample.needed} resolved.`
        : `${s.resolved} live resolved signals published.`;

  return (
    <div className="mt-8 rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-text-primary">Publication status</p>
          <p className="mt-1 max-w-xl text-xs leading-5 text-text-muted">{statusText}</p>
        </div>
        <a
          href={TRACK_RECORD_CSV_URL}
          className="inline-flex items-center gap-2 rounded-lg border border-white/[0.1] bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-text-primary transition-colors hover:bg-white/[0.06]"
        >
          <Download className="h-4 w-4 text-green" aria-hidden="true" />
          Download CSV
        </a>
      </div>

      {s.status === "collecting" && !loading && !failed && (
        <div className="mt-5" aria-hidden="true">
          <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-green/70 transition-[width] duration-700"
              style={{ width: `${Math.max(2, s.sample.progress_pct)}%` }}
            />
          </div>
          <p className="mt-2 text-[10px] uppercase tracking-[0.14em] text-text-muted">
            {s.sample.remaining} more resolved live signals before a headline win rate is published
          </p>
        </div>
      )}

      {s.resolved > 0 && (
        <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            {
              label: "Win rate (TP/SL)",
              value: s.status === "collecting" ? "Collecting" : formatPct(s.win_rate_tp_sl),
            },
            { label: "Avg R net", value: formatR(s.avg_r_net) },
            { label: "Avg R gross", value: formatR(s.avg_r_gross) },
            { label: "Resolved", value: String(s.resolved) },
          ].map((stat) => (
            <div key={stat.label} className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3">
              <dt className="text-[10px] uppercase tracking-[0.14em] text-text-muted">{stat.label}</dt>
              <dd className="mt-1 font-mono text-lg text-text-primary">{stat.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {failed ? (
        <div className="mt-6 flex items-start gap-3 rounded-xl border border-yellow/15 bg-yellow/[0.04] p-5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow" aria-hidden="true" />
          <p className="text-xs leading-5 text-text-muted">
            The live feed could not be reached from this browser. The published CSV is still
            downloadable and is the canonical record.
          </p>
        </div>
      ) : hasRows ? (
        <div className="mt-6 overflow-x-auto rounded-xl border border-white/[0.07]">
          <table className="w-full min-w-[720px] text-sm">
            <caption className="sr-only">Resolved live signals</caption>
            <thead>
              <tr className="border-b border-white/[0.07] text-left text-xs text-text-muted">
                <th scope="col" className="px-4 py-3 font-medium">Closed</th>
                <th scope="col" className="px-4 py-3 font-medium">Symbol</th>
                <th scope="col" className="px-4 py-3 font-medium">Market</th>
                <th scope="col" className="px-4 py-3 font-medium">Direction</th>
                <th scope="col" className="px-4 py-3 font-medium">Outcome</th>
                <th scope="col" className="px-4 py-3 text-right font-medium">R gross</th>
                <th scope="col" className="px-4 py-3 text-right font-medium">R net</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.signal_id} className="border-b border-white/[0.05] last:border-0">
                  <td className="px-4 py-3 text-text-muted">{formatDate(row.closed_at)}</td>
                  <td className="px-4 py-3 text-text-secondary">{row.symbol}</td>
                  <td className="px-4 py-3 capitalize text-text-muted">{row.market}</td>
                  <td className="px-4 py-3 capitalize text-text-secondary">{row.direction}</td>
                  <td className={`px-4 py-3 uppercase ${outcomeClass(row.outcome)}`}>{row.outcome}</td>
                  <td className={`px-4 py-3 text-right font-mono ${outcomeClass(row.outcome)}`}>
                    {formatR(row.r_multiple)}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${outcomeClass(row.outcome)}`}>
                    {formatR(row.r_multiple_net)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-white/[0.12] bg-white/[0.015] p-5">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
            <p className="text-xs leading-5 text-text-muted">
              The first tracked cohort is still open. Rows are added only when a real paper signal
              resolves from live data; simulated and back-filled results are never shown. The CSV
              currently contains the published schema and no rows.
            </p>
          </div>
        </div>
      )}

      <p className="mt-4 text-[10px] leading-5 text-text-muted">
        {s.generated_at ? `As of ${formatDate(s.generated_at)} · ` : ""}
        live-only · net assumes {s.cost_r}R round-trip cost ·{" "}
        <Link href="/track-record" className="text-green/80 underline-offset-2 hover:underline">
          Full ledger and methodology
        </Link>
      </p>
    </div>
  );
}
