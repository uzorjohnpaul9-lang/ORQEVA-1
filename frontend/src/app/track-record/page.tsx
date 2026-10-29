import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, Check, Download } from "lucide-react";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { TrackRecordLive } from "@/components/marketing/TrackRecordLive";
import { TRACK_RECORD_CSV_URL } from "@/lib/track-record";

const siteUrl = "https://orqeva.pages.dev";

export const metadata: Metadata = {
  title: "Track record — ORQEVA",
  description:
    "The public ORQEVA ledger: every resolved live signal, wins and losses, with outcome, R-multiple, methodology and a downloadable CSV.",
  alternates: { canonical: `${siteUrl}/track-record` },
};

const rules = [
  "Entry, stop and target are fixed when a signal is published — never adjusted after the fact.",
  "A signal resolves when it hits target, hits invalidation, or reaches its 72-hour expiry.",
  "Only bars that open after publication are used, so the bar containing the signal cannot leak pre-signal price action.",
  "If one bar spans both target and invalidation, the stop is assumed to fill first — the conservative outcome.",
  "R-multiple is (exit − entry) ÷ (entry − stop), so results are comparable across markets.",
  "Only live-data signals count. Simulated and unknown-provenance rows are excluded and reported separately.",
  "Net R subtracts an assumed 0.05R round-trip cost; gross R is shown alongside it.",
  "The headline win rate is withheld until 30 live signals have resolved. Below that, the ledger shows progress only.",
];

export default function TrackRecordPage() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <MarketingHeader />
      <main>
        <section className="border-b border-white/[0.06] py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-text-muted transition-colors hover:text-text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Back to overview
            </Link>
            <p className="mt-8 text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
              Public ledger
            </p>
            <h1 className="mt-4 max-w-3xl text-balance text-4xl font-semibold tracking-[-0.04em] sm:text-5xl lg:text-6xl">
              Every result, including the ones that lost.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-text-secondary">
              This is the full resolved history of ORQEVA&apos;s paper signals, generated
              from live market data. It is not a highlight reel: the table, the CSV and the
              statistics all come from the same underlying rows, and simulated data is never
              mixed in.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a
                href={TRACK_RECORD_CSV_URL}
                className="inline-flex items-center gap-2 rounded-lg bg-green px-4 py-2.5 text-sm font-semibold text-black transition-opacity hover:opacity-90"
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                Download full CSV
              </a>
              <Link
                href="/#pricing"
                className="inline-flex items-center gap-2 rounded-lg border border-white/[0.12] bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-text-primary transition-colors hover:bg-white/[0.06]"
              >
                See plans
              </Link>
            </div>

            <TrackRecordLive full />
          </div>
        </section>

        <section className="border-b border-white/[0.06] py-16 sm:py-20">
          <div className="mx-auto grid max-w-7xl gap-10 px-5 sm:px-8 lg:grid-cols-[1fr_0.8fr] lg:gap-16">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                Methodology
              </p>
              <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
                How a result is counted.
              </h2>
              <ul className="mt-7 space-y-4">
                {rules.map((rule) => (
                  <li key={rule} className="flex gap-3 text-sm leading-6 text-text-secondary">
                    <Check className="mt-1 h-3.5 w-3.5 shrink-0 text-green" aria-hidden="true" />
                    {rule}
                  </li>
                ))}
              </ul>
            </div>
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-6">
                <h3 className="text-sm font-semibold text-text-primary">What is excluded</h3>
                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  Simulated signals, demo accounts, unknown-provenance legacy rows and any
                  user-specific signal. The public ledger only reads platform-wide signals
                  created from live market data.
                </p>
              </div>
              <div className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-6">
                <h3 className="text-sm font-semibold text-text-primary">What the CSV contains</h3>
                <p className="mt-2 text-sm leading-6 text-text-secondary">
                  One row per resolved live signal: open and close timestamps, symbol, market,
                  direction, entry, stop, target, exit, outcome, gross R, net R, data source and
                  the resolution basis used.
                </p>
              </div>
              <div className="flex items-start gap-2.5 rounded-2xl border border-yellow/15 bg-yellow/[0.04] p-6">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow" aria-hidden="true" />
                <p className="text-sm leading-6 text-text-muted">
                  Past performance does not guarantee future results. Paper results exclude
                  real slippage, financing, gaps and broker-specific fills. Nothing here is
                  investment advice.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </div>
  );
}
