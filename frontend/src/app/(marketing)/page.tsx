import type { Metadata } from "next";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Check,
  ChevronDown,
  Globe2,
  GraduationCap,
  Layers,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { InteractiveMarketChart } from "@/components/marketing/InteractiveMarketChart";
import { SignalPulse } from "@/components/ui/SignalPulse";
import {
  FEATURE_MATRIX,
  PLAN_ANNUAL_PRICES,
  PLAN_PRICES,
  TIERS,
  type FeatureValue,
} from "@/lib/plans";

const siteUrl = "https://orqeva.pages.dev";

const title = "ORQEVA — Signals with context. Execution with guardrails.";
const description =
  "Multi-market trading intelligence across forex, US equities, commodities and crypto. ORQEVA pairs structured signals with explicit risk context and paper-first execution.";
const socialImage = {
  url: `${siteUrl}/og-orqeva.jpg`,
  secureUrl: `${siteUrl}/og-orqeva.jpg`,
  width: 1200,
  height: 630,
  type: "image/jpeg",
  alt: "ORQEVA social preview with a sample EUR/USD signal brief, risk context and guardrails.",
};

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
    images: [socialImage],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: [socialImage],
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
      "Fast-moving markets framed with tighter risk controls and explicit invalidation.",
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
    body: "Web, email and Telegram notifications organised by conviction, market and time horizon.",
  },
  {
    icon: GraduationCap,
    title: "Academy",
    body: "Short lessons that explain signal logic, invalidation and position sizing — not just outcomes.",
  },
];

const principles = [
  {
    title: "Evidence over urgency",
    body: "No countdown timers. No manufactured fear of missing out.",
  },
  {
    title: "Process over prediction",
    body: "A repeatable decision framework matters more than any single call.",
  },
  {
    title: "Survival over streaks",
    body: "The first objective is staying in the game long enough to compound.",
  },
];

const faqs = [
  {
    question: "Is ORQEVA financial advice?",
    answer:
      "No. ORQEVA provides market analysis, signals and execution tools for informational purposes only. You remain responsible for every decision and should consider your own objectives, experience and risk tolerance.",
  },
  {
    question: "Do I need a broker to use ORQEVA?",
    answer:
      "No. You can follow signals and paper trade without connecting a broker. Live auto-trade is optional and requires an explicitly connected account and enabled risk settings.",
  },
  {
    question: "Can I start without risking real money?",
    answer:
      "Yes. Paper trading is the default starting point. It lets you learn the workflow, observe how signals behave and test risk settings before any live capital is involved.",
  },
  {
    question: "How are signals generated?",
    answer:
      "Signals come from a multi-factor process that combines market structure, momentum, volatility filters and event awareness. Most raw setups are rejected. Confidence ranks setups; it is not a guarantee.",
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

const startSteps = [
  {
    number: "01",
    title: "Create your account",
    body: "Use an email, username and password. No card is required, and you can stay on the free plan for as long as you need.",
    icon: Check,
  },
  {
    number: "02",
    title: "Open the Overview",
    body: "Overview is your home base: portfolio value, P&L, open trades and the latest signals in one place.",
    icon: Activity,
  },
  {
    number: "03",
    title: "Practise in paper mode",
    body: "Review a setup, set your risk limits, then place a paper trade. Connect a broker only when the workflow is familiar.",
    icon: ShieldCheck,
  },
];

const dashboardMap = [
  {
    title: "Overview",
    body: "Portfolio value, recent signals, open trades and performance at a glance.",
    icon: Activity,
  },
  {
    title: "AI Signals",
    body: "Structured setups with direction, entry, invalidation, target and confidence.",
    icon: Zap,
  },
  {
    title: "Risk Mgmt",
    body: "Daily loss limits, exposure caps and a kill switch that blocks new orders.",
    icon: ShieldCheck,
  },
  {
    title: "Portfolio",
    body: "Open positions, trade history and the equity curve behind your results.",
    icon: Layers,
  },
  {
    title: "Trading",
    body: "Place orders in paper mode first, then enable live routing only when ready.",
    icon: BarChart3,
  },
  {
    title: "Help & Guide",
    body: "A full walkthrough of signals, risk, brokers, billing and the dashboard.",
    icon: GraduationCap,
  },
];

const tierStyles = {
  Free: "border-white/[0.08] bg-white/[0.04] text-text-secondary",
  Premium: "border-yellow/20 bg-yellow-dim text-yellow",
  VIP: "border-purple/20 bg-purple-dim text-purple",
};

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
          acceptedAnswer: {
            "@type": "Answer",
            text: faq.answer,
          },
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
                  ORQEVA reads structure across forex, US equities,
                  commodities and crypto, then frames each opportunity with
                  entry, invalidation, target and risk — so you can decide with
                  discipline, not urgency.
                </p>

                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link
                    href="/register"
                    className="group inline-flex items-center justify-center gap-2 rounded-lg bg-green px-5 py-3 text-sm font-semibold text-bg-primary transition-[background-color,transform] hover:bg-green/90 active:scale-[0.98]"
                  >
                    Start free
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                  <a
                    href="#how"
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/[0.1] bg-white/[0.02] px-5 py-3 text-sm font-medium text-text-secondary transition-colors hover:border-white/[0.16] hover:bg-white/[0.05] hover:text-text-primary"
                  >
                    See how it works
                  </a>
                </div>

                <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-xs text-text-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green" />
                    No card required
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green" />
                    Paper trading first
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green" />
                    Cancel anytime
                  </span>
                </div>

                <a
                  href="#start-here"
                  className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-green transition-colors hover:text-green/80"
                >
                  New here? Start with the guide
                  <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </div>

              <InteractiveMarketChart />
            </div>

            <div className="mt-16 flex flex-col gap-3 border-t border-white/[0.06] pt-6 text-[11px] uppercase tracking-[0.16em] text-text-muted sm:flex-row sm:items-center sm:justify-between">
              <p>Forex · US equities · Commodities · Digital assets</p>
              <p>Paper-first · Live only when you enable it</p>
            </div>
          </div>
        </section>

        <section
          id="start-here"
          className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28"
        >
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="grid gap-10 lg:grid-cols-[0.82fr_1.18fr] lg:gap-16">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                  New here?
                </p>
                <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                  Three steps from sign-up to your first paper trade.
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  ORQEVA is a workspace, not a feed you scroll and guess from.
                  Start with the account view, learn where the signals and risk
                  controls live, then practise before any live capital is
                  involved.
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                  <Link
                    href="/register"
                    className="group inline-flex items-center justify-center gap-2 rounded-lg bg-green px-5 py-3 text-sm font-semibold text-bg-primary transition-[background-color,transform] hover:bg-green/90 active:scale-[0.98]"
                  >
                    Create free account
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                  <span className="text-xs leading-5 text-text-muted">
                    No card required. Paper trading first.
                  </span>
                </div>
              </div>

              <ol className="space-y-3">
                {startSteps.map((step) => {
                  const Icon = step.icon;

                  return (
                    <li
                      key={step.number}
                      className="group flex gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5 transition-colors hover:border-white/[0.13] sm:p-6"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-green/15 bg-green/[0.07] text-green">
                        <Icon className="h-[18px] w-[18px]" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2.5">
                          <span className="font-mono text-[10px] text-green/70">
                            {step.number}
                          </span>
                          <h3 className="text-sm font-medium text-text-primary">
                            {step.title}
                          </h3>
                        </div>
                        <p className="mt-2 max-w-xl text-sm leading-6 text-text-muted">
                          {step.body}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </div>

            <div className="mt-14">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                    Inside the dashboard
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    The six areas you will use first.
                  </p>
                </div>
                <span className="rounded-full border border-white/[0.08] px-3 py-1 text-[10px] uppercase tracking-[0.12em] text-text-muted">
                  Available after sign-up
                </span>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {dashboardMap.map((item) => {
                  const Icon = item.icon;

                  return (
                    <article
                      key={item.title}
                      className="group rounded-2xl border border-white/[0.07] bg-[#0B0E13] p-5 transition-colors hover:border-white/[0.13]"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-green">
                        <Icon className="h-4 w-4" />
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
                Illustrative guidance only. Signals are informational, not
                financial advice, and confidence does not remove risk.
              </p>
            </div>
          </div>
        </section>

        <section className="border-b border-white/[0.06] py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <div className="max-w-3xl">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-green/80">
                The difference
              </p>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-5xl">
                Most tools hand you an arrow.{" "}
                <span className="text-text-muted">
                  Few tell you what invalidates it.
                </span>
              </h2>
              <p className="mt-5 max-w-2xl text-base leading-7 text-text-secondary">
                A useful signal is more than a direction. It is a thesis, a
                failure point and a sizing decision. ORQEVA is designed around
                that full chain.
              </p>
            </div>

            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {differences.map((item) => (
                <article
                  key={item.number}
                  className="group rounded-2xl border border-white/[0.07] bg-gradient-to-b from-white/[0.035] to-transparent p-6 transition-colors hover:border-white/[0.12]"
                >
                  <div className="flex items-start justify-between">
                    <span className="font-mono text-[11px] text-green/70">
                      {item.number}
                    </span>
                    <ArrowUpRight className="h-4 w-4 text-text-muted/40 transition-colors group-hover:text-green" />
                  </div>
                  <h3 className="mt-8 text-base font-medium text-text-primary">
                    {item.title}
                  </h3>
                  <p className="mt-2.5 text-sm leading-6 text-text-muted">
                    {item.body}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          id="how"
          className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28"
        >
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

        <section
          id="markets"
          className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28"
        >
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
                <ArrowRight className="h-3.5 w-3.5" />
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
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-xl ${market.iconClass}`}
                      >
                        <Icon className="h-[18px] w-[18px]" />
                      </div>
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.12em] ${tierStyles[market.tier]}`}
                      >
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

            <p className="mt-6 text-xs leading-6 text-text-muted">
              Signal coverage and execution access follow your plan. You can
              change tiers from billing without changing your workflow.
            </p>
          </div>
        </section>

        <section
          id="platform"
          className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28"
        >
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
                  <article
                    key={feature.title}
                    className="group bg-[#0B0E13] p-6 transition-colors hover:bg-[#0E1219] sm:p-7"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-green transition-colors group-hover:border-green/20 group-hover:bg-green/[0.05]">
                      <Icon className="h-4 w-4" />
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
                “Confidence is not certainty. Position sizing is where
                conviction becomes discipline.”
              </blockquote>

              <div className="mt-10 grid gap-6 border-t border-white/[0.07] pt-7 sm:grid-cols-3">
                {principles.map((principle) => (
                  <div key={principle.title}>
                    <h2 className="text-sm font-medium text-text-primary">
                      {principle.title}
                    </h2>
                    <p className="mt-2 text-xs leading-5 text-text-muted">
                      {principle.body}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section
          id="pricing"
          className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28"
        >
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
                coverage and faster execution as your workflow matures.
              </p>
            </div>

            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {TIERS.map((tier) => {
                const highlighted = tier.tier === "premium";

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

                    <p className="text-sm font-medium text-text-primary">
                      {tier.name}
                    </p>
                    <p className="mt-1 pr-20 text-xs leading-5 text-text-muted">
                      {tier.tagline}
                    </p>

                    <div className="mt-7 flex items-end gap-2">
                      <span className="text-4xl font-semibold tracking-[-0.04em] text-text-primary">
                        ${PLAN_PRICES[tier.tier]}
                      </span>
                      <span className="pb-1 text-xs text-text-muted">
                        {tier.tier === "free" ? "forever" : "/ 30 days"}
                      </span>
                    </div>
                    <p className="mt-1 min-h-5 text-[11px] text-text-muted">
                      {tier.tier !== "free"
                        ? `$${PLAN_ANNUAL_PRICES[tier.tier]} billed yearly`
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
                      {tier.tier === "free" ? "Start free" : `Choose ${tier.name}`}
                    </Link>

                    <ul className="mt-7 space-y-3 border-t border-white/[0.07] pt-6">
                      {tier.perks.map((perk) => (
                        <li
                          key={perk}
                          className="flex gap-2.5 text-sm leading-5 text-text-secondary"
                        >
                          <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green" />
                          {perk}
                        </li>
                      ))}
                    </ul>
                  </article>
                );
              })}
            </div>

            <p className="mt-5 text-center text-xs text-text-muted">
              You will choose or change your plan after creating an account.
            </p>

            <details className="group mx-auto mt-10 max-w-5xl overflow-hidden rounded-2xl border border-white/[0.07] bg-[#0B0E13]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary sm:px-6 [&::-webkit-details-marker]:hidden">
                Compare every feature
                <ChevronDown className="h-4 w-4 shrink-0 text-text-muted transition-transform group-open:rotate-180" />
              </summary>
              <div className="overflow-x-auto border-t border-white/[0.07]">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06] text-left">
                      <th className="px-5 py-3 text-xs font-medium text-text-muted sm:px-6">
                        Feature
                      </th>
                      {TIERS.map((tier) => (
                        <th
                          key={tier.tier}
                          className="px-5 py-3 text-center text-xs font-medium text-text-muted sm:px-6"
                        >
                          {tier.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {FEATURE_MATRIX.map((row) => (
                      <tr
                        key={row.label}
                        className="border-b border-white/[0.05] last:border-0"
                      >
                        <td className="px-5 py-3 text-text-secondary sm:px-6">
                          {row.label}
                        </td>
                        {TIERS.map((tier) => (
                          <td
                            key={tier.tier}
                            className="px-5 py-3 text-center text-xs text-text-muted sm:px-6"
                          >
                            {renderFeatureValue(row[tier.tier])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        </section>

        <section
          id="faq"
          className="scroll-mt-24 border-b border-white/[0.06] py-20 sm:py-28"
        >
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
                <details
                  key={faq.question}
                  className="group border-b border-white/[0.07] py-5 first:border-t first:border-white/[0.07]"
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-6 [&::-webkit-details-marker]:hidden">
                    <span className="text-sm font-medium text-text-primary sm:text-base">
                      {faq.question}
                    </span>
                    <ChevronDown className="h-4 w-4 shrink-0 text-text-muted transition-transform group-open:rotate-180" />
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
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
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

function renderFeatureValue(value: FeatureValue) {
  if (value === true) {
    return <Check className="mx-auto h-3.5 w-3.5 text-green" aria-label="Included" />;
  }
  if (value === false) {
    return <span aria-label="Not included">—</span>;
  }
  return value;
}
