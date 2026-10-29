import Link from "next/link";
import { SignalPulse } from "@/components/ui/SignalPulse";

const productLinks = [
  { label: "How it works", href: "/#how" },
  { label: "Track record", href: "/track-record" },
  { label: "Markets", href: "/#markets" },
  { label: "Pricing", href: "/#pricing" },
  { label: "About", href: "/#about" },
];

const accountLinks = [
  { label: "Start free", href: "/register" },
  { label: "Sign in", href: "/login" },
  { label: "Support", href: "/support" },
];

const legalLinks = [
  { label: "Terms", href: "/legal/terms" },
  { label: "Privacy", href: "/legal/privacy" },
  { label: "Refund policy", href: "/legal/refunds" },
];

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/[0.06] bg-[#080A0E]">
      <div className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-16">
        <div className="grid gap-12 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div className="max-w-sm">
            <Link href="/" className="inline-flex items-center gap-3" aria-label="ORQEVA home">
              <SignalPulse size={30} rings={2} />
              <span className="text-[13px] font-semibold tracking-[0.28em] text-text-primary">
                ORQEVA
              </span>
            </Link>
            <p className="mt-5 text-sm leading-7 text-text-secondary">
              Multi-market trading intelligence with explicit risk context.
              Built for traders who want a repeatable process, not a promise.
            </p>
            <p className="mt-5 text-[11px] uppercase tracking-[0.18em] text-text-muted">
              Signals with context. Execution with guardrails.
            </p>
          </div>

          <FooterColumn title="Product" links={productLinks} />
          <FooterColumn title="Account" links={accountLinks} />
          <FooterColumn title="Legal" links={legalLinks} />
        </div>

        <div className="mt-14 border-t border-white/[0.06] pt-8">
          <p className="max-w-5xl text-xs leading-6 text-text-muted">
            ORQEVA provides market analysis, signals and execution tools for
            informational purposes only. Nothing on this site is financial,
            investment or tax advice, and no outcome is guaranteed. Trading
            leveraged products and digital assets involves substantial risk of
            loss. Only risk capital you can afford to lose. Illustrative
            product visuals are not live recommendations or performance claims.
          </p>
          <div className="mt-6 flex flex-col gap-3 text-xs text-text-muted sm:flex-row sm:items-center sm:justify-between">
            <p>&copy; {new Date().getFullYear()} ORQEVA. All rights reserved.</p>
            <p>Built for disciplined decision-making.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  links,
}: {
  title: string;
  links: { label: string; href: string }[];
}) {
  return (
    <div>
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        {title}
      </h2>
      <ul className="mt-5 space-y-3">
        {links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              className="text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
