import type { Metadata } from "next";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Building2,
  Check,
  ChevronDown,
  FileText,
  Globe2,
  GraduationCap,
  Layers,
  Lock,
  MessageCircle,
  Scale,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { SignalBrief } from "@/components/marketing/SignalBrief";
import { SignalPulse } from "@/components/ui/SignalPulse";
import {
  FEATURE_MATRIX,
  PLAN_ANNUAL_PRICES,
  PLAN_PRICES,
  TIERS,
  type FeatureValue,
  type Tier,
} from "@/lib/plans";
import { TrackRecordLive } from "@/components/marketing/TrackRecordLive";

const siteUrl = "https://orqeva.pages.dev";

const title = "ORQEVA — Signals with context. Execution with guardrails.";
const description =
  "Multi-market trading intelligence across forex, US equities, commodities and crypto. ORQEVA pairs structured signals with explicit risk context and paper-first execution.";

export const metadata: Metadata = {
  title: { absolute: title },
  description,
  alternates: { canonical: `${siteUrl}/` },
  openGraph: {
    title,
    description,
    url: `${siteUrl}/`,
    siteName: "ORQEVA",
    type: "website",
    locale: "en_US",
    images: [
      {
        url: `${siteUrl}/og-orqeva.jpg`,
        width: 1200,
        height: 630,
        type: "image/jpeg",
        alt: "ORQEVA social preview with a sample EUR/USD signal brief, risk context and guardrails.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: [`${siteUrl}/og-orqeva.jpg`],
  },
  robots: { index: true, follow: true },
};

type Market = {
  name: string;
  coverage: string;
  session: string;
  description: string;
  tier: "Free" | "Premium" | "VIP";
  icon: LucideIcon;
  iconClass: string;
};

const markets: Market[] = [
  {
    name: "Forex",
    coverage: "G10 majors & crosses",
    session: "24/5",
    description:
      "Session-aware trend and momentum setups across the most liquid currency pairs.",
    tier: "Free",
    icon: Globe2,
    iconClass: "bg-green-dim text-green",
  },
  {
    name: "US equities",
    coverage: "Liquid large caps",
    session: "Market hours",
    description:
      "Structured setups with event awareness for earnings, volatility and opening ranges.",
    tier: "Premium",
    icon: BarChart3,
    iconClass: "bg-yellow-dim text-yellow",
  },
  {
    name: "Commodities",
    coverage: "Metals & energy",
    session: "Event-sensitive",
    description:
      "Context for gold, silver and crude when macro data and positioning collide.",
    tier: "Premium",
    icon: Layers,
    iconClass: "bg-yellow-dim text-yellow",
  },
  {
    name: "Digital assets",
    coverage: "Majors & select alts",
    session: "24/7",
    description:
      "Majors and select alts, with memecoins gated behind VIP and excluded from default automation. Crypto auto-trade is opt-in, paper-first, and bound by the same daily-loss and exposure caps as every other market.",
    tier: "VIP",
    icon: Zap,
    iconClass: "bg-purple-dim text-purple",
  },
];

const differences = [
  {
    number: "01",
    title: "Context before calls",
    body: "Every setup carries its reasoning: trend, momentum, volatility, session and event risk. You see the thesis, not just the arrow.",
  },
  {
    number: "02",
    title: "Invalidation is explicit",
    body: "Entry, stop and target are defined before size. Risk is part of the signal, not an afterthought in a separate spreadsheet.",
  },
  {
    number: "03",
    title: "Automation with consent",
    body: "Start in paper. Graduate to live routing only when your settings, evidence and risk limits agree.",
  },
];

const steps = [
  {
    number: "01",
    title: "Observe",
    body: "Multi-market structure, momentum, volatility and the macro calendar are read together.",
  },
  {
    number: "02",
    title: "Qualify",
    body: "Weak, late or event-exposed setups are rejected before they ever become a signal.",
  },
  {
    number: "03",
    title: "Frame",
    body: "Accepted ideas get an entry, invalidation, target, reward-to-risk ratio, confidence and expiry.",
  },
  {
    number: "04",
    title: "Act",
    body: "Follow manually, receive ranked alerts, or route to a connected broker with risk gates active.",
  },
];

const features = [
  {
    icon: Activity,
    title: "Signal engine",
    body: "Multi-factor setups across trend, momentum, volatility and structure — not single-indicator triggers.",
  },
  {
    icon: ShieldCheck,
    title: "Risk engine",
    body: "Exposure caps, daily-loss limits and portfolio-level guardrails that stay between you and impulse.",
  },
  {
    icon: Zap,
    title: "Execution",
    body: "Paper trading first, then broker routing with explicit consent and position-level controls.",
  },
  {
    icon: Globe2,
    title: "Unified coverage",
    body: "Forex, US equities, commodities and crypto in one workflow, with coverage that follows your plan.",
  },
  {
    icon: Bell,
    title: "Ranked alerts",
    body: "Web and Telegram notifications organised by conviction, market and time horizon.",
  },
  {
    icon: GraduationCap,
    title: "Academy",
    body: "Short lessons that explain signal logic, invalidation and position sizing — not just outcomes.",
  },
];

const confidenceItems = [
  {
    title: "What it measures",
    body: "How cleanly a setup met the engine's criteria: higher-timeframe alignment, momentum agreement, volatility regime, session timing and event risk.",
  },
  {
    title: "What it does not mean",
    body: "It is not a probability of profit, a win-rate forecast, or a position size. It ranks one setup against another; it does not predict the outcome.",
  },
  {
    title: "How to use it",
    body: "Treat the score as a filter for attention, not a reason to over-size. Judge it against resolved outcomes in the public track record.",
  },
];

const trackRecordRules = [
  "Entry, stop and target are fixed when a signal is published — never adjusted after the fact.",
  "A signal resolves when it hits target, hits invalidation, or reaches its stated expiry.",
  "R-multiple is (exit − entry) ÷ (entry − stop), so every result is comparable across markets.",
  "Only live-data signals count toward the public ledger; simulated and unknown-provenance rows are excluded and reported separately.",
  "Every resolved live signal is appended to the log and the CSV, wins and losses alike — never back-filled or hand-picked.",
];

const dashboardAreas = [
  { title: "Overview", body: "Portfolio value, recent signals, open trades and performance at a glance.", icon: Activity },
  { title: "AI Signals", body: "Structured setups with direction, entry, invalidation, target and confidence.", icon: Zap },
  { title: "Risk", body: "Daily loss limits, exposure caps and a kill switch that blocks new orders.", icon: ShieldCheck },
  { title: "Portfolio", body: "Open positions, trade history and the equity curve behind your results.", icon: Layers },
  { title: "Trading", body: "Place orders in paper mode first, then enable live routing only when ready.", icon: BarChart3 },
  { title: "Help & Guide", body: "A full walkthrough of signals, risk, brokers, billing and the dashboard.", icon: GraduationCap },
];

const aboutCards = [
  {
    icon: Building2,
    title: "Company",
    body: "ORQEVA is a product of MUNA TRADING, an independent software company building trading decision-support tools.",
  },
  {
    icon: MessageCircle,
    title: "Contact",
    body: "Support and account questions are handled directly on Telegram at @Johnpaulmuna_83. Billing and privacy requests use the same channel.",
  },
  {
    icon: FileText,
    title: "Documents",
    body: "Terms, privacy and refund policies are published and linked in the footer. Material changes are announced in-app.",
  },
];

const legalPoints = [
  {
    title: "Not a broker or adviser",
    body: "ORQEVA is not a broker-dealer, investment adviser or asset manager. We do not manage money and cannot withdraw from your accounts.",
  },
  {
    title: "Paid signals are informational",
    body: "Subscriptions buy access to analysis and tooling, not a promise of returns. Signals and outputs are not financial, investment, legal or tax advice.",
  },
  {
    title: "Live automation is opt-in",
    body: "Auto-trade is off by default. Live routing requires a connection you create with trade-only credentials and explicit risk settings you control.",
  },
  {
    title: "Jurisdiction is your responsibility",
    body: "Rules for paid signals and automated execution vary by country. Confirm that using ORQEVA is permitted where you live before subscribing or enabling live trading.",
  },
];

const faqs = [
  {
    question: "Is ORQEVA financial advice?",
    answer:
      "No. ORQEVA provides market analysis, signals and execution tools for informational purposes only. You remain responsible for every decision and should consider your own objectives, experience and risk tolerance.",
  },
  {
    question: "What does the confidence score actually mean?",
    answer:
      "It is a 0–100 rank of how cleanly a setup met our criteria. It is not a probability of profit or a win-rate forecast, and it does not set your position size. See the confidence explainer above and judge the score against the published track record.",
  },
  {
    question: "Do you publish your results?",
    answer:
      "Yes. Every resolved live signal is logged with timestamps, outcome and R-multiple, and the full log is downloadable as CSV. Simulated data is excluded, and the headline win rate is withheld until 30 live signals have resolved. No results are invented or back-filled.",
  },
  {
    question: "Do I need a broker to use ORQEVA?",
    answer:
      "No. You can follow signals and paper trade without connecting a broker. Live auto-trade is optional and requires an explicitly connected account and enabled risk settings.",
  },
  {
    question: "Are memecoins auto-traded?",
    answer:
      "Not by default. Memecoins are VIP-only, excluded from default automation, and can gap or lose liquidity quickly. Enabling them requires an explicit opt-in and is subject to the same daily-loss and exposure caps as other markets.",
  },
  {
    question: "How does billing work?",
    answer:
      "Paid plans are billed per 30-day period, not per calendar month. Yearly plans are charged once for 12 months: $490 instead of $588 for Premium and $1,990 instead of $2,388 for VIP.",
  },
  {
    question: "Which markets are covered?",
    answer:
      "Free includes forex. Premium adds US equities and commodities. VIP adds crypto and select memecoins. Coverage, alert latency and execution access follow your subscription tier.",
  },
  {
    question: "Can I change or cancel my plan?",
    answer:
      "Yes. You can manage your subscription from billing. Plan changes take effect according to the billing cycle shown at checkout, and no long-term contract is required.",
  },
];

const tierStyles = {
  Free: "border-white/[0.08] bg-white/[0.04] text-text-secondary",
  Premium: "border-yellow/20 bg-yellow-dim text-yellow",
  VIP: "border-purple/20 bg-purple-dim text-purple",
};

const annualSaving = (tier: Tier) =>
  PLAN_PRICES[tier] * 12 - PLAN_ANNUAL_PRICES[tier];

function money(value: number) {
  return value.toLocaleString("en-US");
}

export default function LandingPage() {
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        name: "ORQEVA",
        applicationCategory: "FinanceApplication",
        operatingSystem: "Web",
        url: `${siteUrl}/`,
        description,
        offers: TIERS.map((tier) => ({
          "@type": "Offer",
          name: tier.name,
          price: PLAN_PRICES[tier.tier],
          priceCurrency: "USD",
          availability: "https://schema.org/InStock",
          url: `${siteUrl}/register`,
        })),
      },
      {
        "@type": "FAQPage",
        mainEntity: faqs.map((faq) => ({
          "@type": "Question",
          name: faq.question,
          acceptedAnswer: { "@type": "Answer", text: faq.answer },
        })),
      },
    ],
  };

  return (
    <div className="min-h-dvh bg-[#090B0F] text-text-primary">
      <MarketingHeader />

      <main>
        <section className="relative isolate overflow-hidden border-b border-white/[0.06]">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10 opacity-60"
            style={{
              backgroundImage:
                "linear-gradient(to right, rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.035) 1px, transparent 1px)",
              backgroundSize: "56px 56px",
              maskImage: "linear-gradient(to bottom, black, transparent 84%)",
              WebkitMaskImage:
                "linear-gradient(to bottom, black, transparent 84%)",
            }}
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-64 left-1/2 -z-10 h-[720px] w-[1100px] -translate-x-1/2 rounded-full"
            style={{
              background:
                "radial-gradient(circle, rgba(0,214,143,0.12), transparent 66%)",
            }}
          />

          <div className="mx-auto max-w-7xl px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:pt-28">
            <div className="grid items-center gap-14 lg:grid-cols-[1.03fr_0.97fr] lg:gap-12">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-green/20 bg-green/[0.06] px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.2em] text-green">
                  <span className="h-1.5 w-1.5 rounded-full bg-green animate-pulse-dot" />
                  Multi-market intelligence
                </div>

                <h1 className="mt-6 max-w-2xl text-balance text-[2.8rem] font-semibold leading-[1.03] tracking-[-0.045em] sm:text-6xl lg:text-[4.4rem]">
                  Signals with context.
                  <span className="block text-text-muted">
                    Execution with guardrails.
                  </span>
                </h1>

                <p className="mt-6 max-w-xl text-base leading-7 text-text-secondary sm:text-lg sm:leading-8">
                  ORQEVA reads structure across forex, US equities, commodities
                  and crypto, then frames each opportunity with entry,
                  invalidation, target and risk — so you can decide with
                  discipline, not urgency.
                </p>

                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link
                    href="/register"
                    className="group inline-flex items-center justify-center gap-2 rounded-lg bg-green px-5 py-3 text-sm font-semibold text-bg-primary transition-[background-color,transform] hover:bg-green/90 active:scale-[0.98]"
                  >
                    Start free
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                  </Link>
                  <a
                    href="#track-record"
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/[0.1] bg-white/[0.02] px-5 py-3 text-sm font-medium text-text-secondary transition-colors hover:border-white/[0.16] hover:bg-white/[0.05] hover:text-text-primary"
                  >
                    See the track record
                  </a>
                </div>

                <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-xs text-text-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green" aria-hidden="true" />
                    No card required
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green" aria-hidden="true" />
                    Paper trading first
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green" aria-hidden="true" />
                    Cancel anytime
                  </span>
                </div>
              </div>

              <SignalBrief />
            </div>

            <div className="mt-16 flex flex-col gap-3 border-t border-white/[0.06] pt-6 text-[11px] uppercase tracking-[0.16em] text-text-muted sm:flex-row sm:items-center sm:justify-between">
              <p>Forex · US equities · Commodities · Digital assets</p>
              <p>Paper-first · Live only when you enable it</p>
            </div>
          </div>
        </section>

        <section className="border-b border-white/[0.06] py-16 sm:py-20">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="grid gap-4 md:grid-cols-3">
              {differences.map((item) => (
                <article
                  key={item.number}
                  className="group rounded-2xl border border-white/[0.07] bg-gradient-to-b from-white/[0.035] to-transparent p-6 transition-colors hover:border-white/[0.12]"
                >
                  <div className="flex items-start justify-between">
                    <span className="font-mono text-[11px] text-green/70">
                      {item.number}
                    </span>
                    <ArrowUpRight className="h-4 w-4 text-text-muted/40 transition-colors group-hover:text-green" aria-hidden="true" />
                  </div>
                  <h2 className="mt-8 text-base font-medium text-text-primary">
                    {item.title}
                  </h2>
                  <p className="mt-2.5 text-sm leading-6 text-text-muted">
                    {item.body}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                How it works
              </p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                Every signal starts with what could prove it wrong.
              </h2>
              <p className="mt-5 text-base leading-7 text-text-secondary">
                The workflow moves from observation to action — but only after a
                setup survives structure, volatility and event-risk filters.
              </p>
              <div className="mt-8 rounded-2xl border border-green/[0.15] bg-green/[0.035] p-5">
                <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-green/80">
                  Design principle
                </p>
                <p className="mt-2.5 text-sm leading-6 text-text-secondary">
                  The engine is built to reject more setups than it publishes.
                  Selectivity is a feature, not a shortage.
                </p>
              </div>
            </div>

            <ol>
              {steps.map((step, index) => (
                <li
                  key={step.number}
                  className={`grid grid-cols-[42px_1fr] gap-5 py-7 ${
                    index === steps.length - 1
                      ? "border-y border-white/[0.07]"
                      : "border-t border-white/[0.07]"
                  }`}
                >
                  <span className="font-mono text-[11px] text-green/60">
                    {step.number}
                  </span>
                  <div>
                    <h3 className="text-lg font-medium text-text-primary">
                      {step.title}
                    </h3>
                    <p className="mt-2 max-w-xl text-sm leading-6 text-text-muted">
                      {step.body}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="confidence" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-8 lg:grid-cols-[0.95fr_1.05fr] lg:gap-16">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                Confidence, explained
              </p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                What &ldquo;82 confidence&rdquo; actually means.
              </h2>
              <p className="mt-5 text-base leading-7 text-text-secondary">
                Confidence is a rank, not a promise. It tells you how cleanly a
                setup met the engine&rsquo;s filters relative to other setups —
                nothing more. Two signals can share a score and resolve in
                opposite directions.
              </p>
              <p className="mt-4 text-base leading-7 text-text-secondary">
                Because a score is only useful if it is checked against reality,
                we publish resolved outcomes in the track record below, with the
                winning and losing trades shown side by side.
              </p>
              <a
                href="#track-record"
                className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-green transition-colors hover:text-green/80"
              >
                See how the score has performed
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </a>
            </div>

            <div className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-6 sm:p-8">
              <div className="flex items-center gap-5">
                <div
                  className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full"
                  style={{
                    background:
                      "conic-gradient(var(--color-green) 82%, rgba(255,255,255,0.07) 0)",
                  }}
                  aria-label="Illustrative confidence rank: 82 out of 100"
                >
                  <div className="flex h-[76px] w-[76px] flex-col items-center justify-center rounded-full bg-[#0B0E13]">
                    <span className="text-2xl font-semibold leading-none text-text-primary">
                      82
                    </span>
                    <span className="mt-1 text-[9px] uppercase tracking-[0.14em] text-text-muted">
                      rank / 100
                    </span>
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">
                    Rank, not probability
                  </p>
                  <p className="mt-1.5 text-xs leading-5 text-text-muted">
                    A high rank means the setup was unusually clean. It does not
                    mean the trade is likely to win.
                  </p>
                </div>
              </div>

              <div className="mt-7 space-y-5 border-t border-white/[0.07] pt-6">
                {confidenceItems.map((item) => (
                  <div key={item.title}>
                    <h3 className="text-sm font-medium text-text-primary">
                      {item.title}
                    </h3>
                    <p className="mt-1.5 text-sm leading-6 text-text-muted">
                      {item.body}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="track-record" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="grid gap-10 lg:grid-cols-[1fr_0.85fr] lg:gap-16">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                  Track record
                </p>
                <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                  A record you can audit, not a highlight reel.
                </h2>
                <p className="mt-5 max-w-2xl text-base leading-7 text-text-secondary">
                  Every signal is timestamped when published and resolved when it
                  reaches target, invalidation or expiry. We publish the complete
                  live log — wins and losses — with the methodology and a
                  downloadable CSV, so the confidence score can be judged against
                  actual outcomes. Simulated data is excluded.
                </p>

                <TrackRecordLive />
              </div>

              <div className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-6 sm:p-7">
                <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-muted">
                  Methodology
                </p>
                <ul className="mt-5 space-y-4">
                  {trackRecordRules.map((rule) => (
                    <li key={rule} className="flex gap-3 text-sm leading-6 text-text-secondary">
                      <Check className="mt-1 h-3.5 w-3.5 shrink-0 text-green" aria-hidden="true" />
                      {rule}
                    </li>
                  ))}
                </ul>
                <div className="mt-6 flex items-start gap-2.5 rounded-xl border border-yellow/15 bg-yellow/[0.04] p-4">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow" aria-hidden="true" />
                  <p className="text-xs leading-5 text-text-muted">
                    Past results do not guarantee future outcomes. Paper results
                    exclude real slippage, financing and broker-specific fills.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="markets" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
              <div className="max-w-2xl">
                <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                  Coverage
                </p>
                <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                  One desk. Four markets.{" "}
                  <span className="text-text-muted">One risk language.</span>
                </h2>
              </div>
              <a
                href="#pricing"
                className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-green transition-colors hover:text-green/80"
              >
                Compare coverage
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </a>
            </div>

            <div className="mt-12 grid gap-4 sm:grid-cols-2">
              {markets.map((market) => {
                const Icon = market.icon;
                return (
                  <article
                    key={market.name}
                    className="group rounded-2xl border border-white/[0.07] bg-[#0C0F14] p-6 transition-colors hover:border-white/[0.13] sm:p-7"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${market.iconClass}`}>
                        <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
                      </div>
                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.12em] ${tierStyles[market.tier]}`}>
                        {market.tier}
                      </span>
                    </div>
                    <div className="mt-7 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <h3 className="text-xl font-medium text-text-primary">
                        {market.name}
                      </h3>
                      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
                        {market.session}
                      </span>
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-[0.13em] text-text-muted">
                      {market.coverage}
                    </p>
                    <p className="mt-4 max-w-lg text-sm leading-6 text-text-secondary">
                      {market.description}
                    </p>
                  </article>
                );
              })}
            </div>

            <div className="mt-6 flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-green" aria-hidden="true" />
              <p className="text-xs leading-6 text-text-muted">
                Memecoins and crypto auto-trade sit at the highest end of the risk
                spectrum. They are off by default, gated behind VIP, and cannot
                override daily-loss, exposure or open-trade limits. Survival
                over streaks applies most where volatility is highest.
              </p>
            </div>
          </div>
        </section>

        <section id="platform" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="max-w-2xl">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                The platform
              </p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                From observation to execution, without losing the plot.
              </h2>
              <p className="mt-5 text-base leading-7 text-text-secondary">
                Each layer has one job. Together they keep the decision, the
                size and the exit connected.
              </p>
            </div>

            <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => {
                const Icon = feature.icon;
                return (
                  <article key={feature.title} className="group bg-[#0B0E13] p-6 transition-colors hover:bg-[#0E1219] sm:p-7">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-green transition-colors group-hover:border-green/20 group-hover:bg-green/[0.05]">
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <h3 className="mt-6 text-base font-medium text-text-primary">
                      {feature.title}
                    </h3>
                    <p className="mt-2.5 text-sm leading-6 text-text-muted">
                      {feature.body}
                    </p>
                  </article>
                );
              })}
            </div>

            <div className="mt-12">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                    Inside the workspace
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    Six areas you will use first.
                  </p>
                </div>
                <Link
                  href="/login"
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-green transition-colors hover:text-green/80"
                >
                  Open the live dashboard
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                </Link>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {dashboardAreas.map((item) => {
                  const Icon = item.icon;
                  return (
                    <article key={item.title} className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-5">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-green">
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </div>
                      <h3 className="mt-5 text-sm font-medium text-text-primary">
                        {item.title}
                      </h3>
                      <p className="mt-1.5 text-xs leading-5 text-text-muted">
                        {item.body}
                      </p>
                    </article>
                  );
                })}
              </div>
              <p className="mt-4 text-xs leading-6 text-text-muted">
                Workspace descriptions are illustrative. Sign in to see the live
                product; dashboard screenshots are published only when they
                reflect the current build.
              </p>
            </div>
          </div>
        </section>

        <section className="border-b border-white/[0.06] py-16 sm:py-20">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="relative overflow-hidden rounded-[28px] border border-white/[0.08] bg-[#0C1016] p-7 sm:p-10 lg:p-12">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -right-24 -top-32 h-80 w-80 rounded-full"
                style={{
                  background:
                    "radial-gradient(circle, rgba(0,214,143,0.12), transparent 68%)",
                }}
              />
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                Operating principle
              </p>
              <blockquote className="mt-5 max-w-4xl text-balance text-2xl font-medium leading-tight tracking-[-0.025em] text-text-primary sm:text-3xl lg:text-4xl">
                &ldquo;Confidence is not certainty. Position sizing is where
                conviction becomes discipline.&rdquo;
              </blockquote>
              <div className="mt-10 grid gap-6 border-t border-white/[0.07] pt-7 sm:grid-cols-3">
                <div>
                  <h2 className="text-sm font-medium text-text-primary">Evidence over urgency</h2>
                  <p className="mt-2 text-xs leading-5 text-text-muted">No countdown timers. No manufactured fear of missing out.</p>
                </div>
                <div>
                  <h2 className="text-sm font-medium text-text-primary">Process over prediction</h2>
                  <p className="mt-2 text-xs leading-5 text-text-muted">A repeatable decision framework matters more than any single call.</p>
                </div>
                <div>
                  <h2 className="text-sm font-medium text-text-primary">Survival over streaks</h2>
                  <p className="mt-2 text-xs leading-5 text-text-muted">The first objective is staying in the game long enough to compound.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="pricing" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                Access
              </p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                Start free. Upgrade when the process earns it.
              </h2>
              <p className="mt-5 text-base leading-7 text-text-secondary">
                No performance promises. No long-term contract. Just broader
                coverage and faster delivery as your workflow matures.
              </p>
            </div>

            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {TIERS.map((tier) => {
                const highlighted = tier.tier === "premium";
                const paid = tier.tier !== "free";
                return (
                  <article
                    key={tier.tier}
                    className={`relative flex flex-col overflow-hidden rounded-2xl border p-6 sm:p-7 ${
                      highlighted
                        ? "border-green/30 bg-[linear-gradient(180deg,rgba(0,214,143,0.075),rgba(255,255,255,0.015))]"
                        : "border-white/[0.07] bg-[#0B0E13]"
                    }`}
                  >
                    {highlighted && (
                      <span className="absolute right-5 top-5 rounded-full border border-green/20 bg-green/[0.08] px-2.5 py-1 text-[9px] font-medium uppercase tracking-[0.14em] text-green">
                        Balanced access
                      </span>
                    )}
                    <p className="text-sm font-medium text-text-primary">{tier.name}</p>
                    <p className="mt-1 pr-20 text-xs leading-5 text-text-muted">{tier.tagline}</p>
                    <div className="mt-7 flex items-end gap-2">
                      <span className="text-4xl font-semibold tracking-[-0.04em] text-text-primary">
                        ${PLAN_PRICES[tier.tier]}
                      </span>
                      <span className="pb-1 text-xs text-text-muted">
                        {paid ? "/ 30 days" : "forever"}
                      </span>
                    </div>
                    <p className="mt-1 min-h-5 text-[11px] text-text-muted">
                      {paid
                        ? `or $${money(PLAN_ANNUAL_PRICES[tier.tier])}/year — save $${money(annualSaving(tier.tier))} vs 12 monthly payments`
                        : "No card required"}
                    </p>
                    <Link
                      href="/register"
                      className={`mt-7 inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                        highlighted
                          ? "bg-green text-bg-primary hover:bg-green/90"
                          : "border border-white/[0.1] bg-white/[0.03] text-text-primary hover:bg-white/[0.06]"
                      }`}
                    >
                      {paid ? `Choose ${tier.name}` : "Start free"}
                    </Link>
                    <ul className="mt-7 space-y-3 border-t border-white/[0.07] pt-6">
                      {tier.perks.map((perk) => (
                        <li key={perk} className="flex gap-2.5 text-sm leading-5 text-text-secondary">
                          <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green" aria-hidden="true" />
                          {perk}
                        </li>
                      ))}
                    </ul>
                  </article>
                );
              })}
            </div>

            <p className="mt-5 text-center text-xs leading-6 text-text-muted">
              Billing periods are 30 days, not calendar months. Yearly plans are
              charged once for 12 months. You choose or change your plan after
              creating an account.
            </p>

            <details className="group mx-auto mt-10 max-w-5xl overflow-hidden rounded-2xl border border-white/[0.07] bg-[#0B0E13]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary sm:px-6 [&::-webkit-details-marker]:hidden">
                Compare every feature
                <ChevronDown className="h-4 w-4 shrink-0 text-text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div className="overflow-x-auto border-t border-white/[0.07]">
                <table className="w-full min-w-[680px] text-sm">
                  <caption className="sr-only">Plan feature comparison</caption>
                  <thead>
                    <tr className="border-b border-white/[0.06] text-left">
                      <th scope="col" className="px-5 py-3 text-xs font-medium text-text-muted sm:px-6">
                        Feature
                      </th>
                      {TIERS.map((tier) => (
                        <th key={tier.tier} scope="col" className="px-5 py-3 text-center text-xs font-medium text-text-muted sm:px-6">
                          {tier.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {FEATURE_MATRIX.map((row) => (
                      <tr key={row.label} className="border-b border-white/[0.05] last:border-0">
                        <th scope="row" className="px-5 py-3 text-left font-normal text-text-secondary sm:px-6">
                          {row.label}
                        </th>
                        {TIERS.map((tier) => (
                          <td key={tier.tier} className="px-5 py-3 text-center text-xs text-text-muted sm:px-6">
                            <FeatureCell value={row[tier.tier]} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            <p className="mx-auto mt-4 max-w-3xl text-center text-xs leading-6 text-text-muted">
              &ldquo;API requests / min&rdquo; is the number of calls your account
              key can make to the ORQEVA API per minute for integrations. It does
              not limit dashboard use or signal delivery.
            </p>
          </div>
        </section>

        <section id="about" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                  About ORQEVA
                </p>
                <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                  Who runs the desk behind the signals.
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  ORQEVA is built by a small, independent team focused on one
                  problem: making trading decisions more structured and less
                  impulsive. We publish our methodology and our terms because
                  trust should be inspectable.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {aboutCards.map((card) => {
                  const Icon = card.icon;
                  return (
                    <article key={card.title} className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-green">
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </div>
                      <h3 className="mt-5 text-sm font-medium text-text-primary">
                        {card.title}
                      </h3>
                      <p className="mt-1.5 text-xs leading-5 text-text-muted">
                        {card.body}
                      </p>
                    </article>
                  );
                })}
              </div>
            </div>

            <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {legalPoints.map((point) => (
                <article key={point.title} className="rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-5">
                  <div className="flex items-center gap-2.5">
                    <Scale className="h-4 w-4 text-green" aria-hidden="true" />
                    <h3 className="text-sm font-medium text-text-primary">{point.title}</h3>
                  </div>
                  <p className="mt-2.5 text-xs leading-5 text-text-muted">{point.body}</p>
                </article>
              ))}
            </div>
            <div className="mt-6 flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.015] p-5">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
              <p className="text-xs leading-6 text-text-muted">
                We are reviewing signals-for-pay and automated-execution
                disclosures against the rules in the jurisdictions we serve.
                Nothing on this page is legal advice. See the{" "}
                <Link href="/legal/terms" className="text-green hover:text-green/80">Terms</Link>,{" "}
                <Link href="/legal/privacy" className="text-green hover:text-green/80">Privacy Policy</Link>{" "}
                and{" "}
                <Link href="/legal/refunds" className="text-green hover:text-green/80">Refund Policy</Link>.
              </p>
            </div>
          </div>
        </section>

        <section id="faq" className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-8 lg:grid-cols-[0.75fr_1.25fr] lg:gap-16">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                Questions
              </p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl">
                Clear answers before you commit.
              </h2>
              <p className="mt-5 text-sm leading-7 text-text-secondary">
                ORQEVA is a decision-support platform, not a promise of returns.
                These are the boundaries that matter most.
              </p>
            </div>
            <div>
              {faqs.map((faq) => (
                <details key={faq.question} className="group border-b border-white/[0.07] py-5 first:border-t first:border-white/[0.07]">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-6 [&::-webkit-details-marker]:hidden">
                    <span className="text-sm font-medium text-text-primary sm:text-base">
                      {faq.question}
                    </span>
                    <ChevronDown className="h-4 w-4 shrink-0 text-text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
                  </summary>
                  <p className="max-w-3xl pt-3 text-sm leading-7 text-text-muted">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden py-20 sm:py-28">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-1/2 h-[500px] w-[850px] -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{
              background:
                "radial-gradient(circle, rgba(0,214,143,0.1), transparent 68%)",
            }}
          />
          <div className="relative mx-auto max-w-4xl px-5 text-center sm:px-8">
            <SignalPulse size={44} rings={3} className="mx-auto" />
            <h2 className="mt-7 text-balance text-3xl font-semibold tracking-[-0.035em] text-text-primary sm:text-5xl">
              Build a process you can repeat.
            </h2>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-text-secondary">
              Start with paper. Learn the rhythm. Connect live capital only when
              the evidence earns it.
            </p>
            <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
              <Link
                href="/register"
                className="group inline-flex items-center justify-center gap-2 rounded-lg bg-green px-5 py-3 text-sm font-semibold text-bg-primary transition-colors hover:bg-green/90"
              >
                Start free
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center justify-center rounded-lg border border-white/[0.1] bg-white/[0.02] px-5 py-3 text-sm font-medium text-text-secondary transition-colors hover:bg-white/[0.05] hover:text-text-primary"
              >
                Sign in
              </Link>
            </div>
            <p className="mx-auto mt-8 max-w-2xl text-[11px] leading-5 text-text-muted">
              Trading involves substantial risk. ORQEVA does not guarantee
              outcomes, and nothing on this site is financial advice.
            </p>
          </div>
        </section>
      </main>

      <MarketingFooter />

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
    </div>
  );
}

function FeatureCell({ value }: { value: FeatureValue }) {
  if (value === true) {
    return (
      <span className="inline-flex items-center justify-center">
        <Check className="h-3.5 w-3.5 text-green" aria-hidden="true" />
        <span className="sr-only">Included</span>
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="inline-flex items-center justify-center">
        <span aria-hidden="true">—</span>
        <span className="sr-only">Not included</span>
      </span>
    );
  }
  return <span>{value}</span>;
}
