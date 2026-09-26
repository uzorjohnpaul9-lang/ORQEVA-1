"use client";

import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const SECTIONS = [
  { id: "getting-started", label: "Getting Started" },
  { id: "tiers", label: "Plans & Tiers" },
  { id: "signals", label: "AI Signals" },
  { id: "trading", label: "Trading & Order Routing" },
  { id: "exchanges", label: "Connecting a Broker" },
  { id: "risk", label: "Risk Management" },
  { id: "telegram", label: "Telegram Alerts" },
  { id: "billing", label: "Billing & Payments" },
  { id: "faq", label: "FAQ" },
];

function Step({ n, title, children }: { n: number; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="shrink-0 w-6 h-6 rounded-full bg-green/20 text-green text-xs font-bold flex items-center justify-center mt-0.5">
        {n}
      </span>
      <div>
        <p className="text-sm font-medium">{title}</p>
        {children && <div className="text-sm text-text-secondary mt-0.5 space-y-1">{children}</div>}
      </div>
    </li>
  );
}

export default function HelpPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Help & Guide</h1>
        <p className="text-sm text-text-secondary mt-1">
          Everything you need to navigate ORQEVA — from your first login to live broker routing.
        </p>
      </div>

      {/* quick jump */}
      <Card padding={false}>
        <div className="flex flex-wrap gap-2 p-4">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="text-xs px-3 py-1.5 rounded-full border border-border text-text-secondary hover:text-text-primary hover:border-green/50 transition-colors"
            >
              {s.label}
            </a>
          ))}
        </div>
      </Card>

      {/* Getting started */}
      <Card className="scroll-mt-20">
        <span id="getting-started" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Getting Started</CardTitle></CardHeader>
        <ol className="space-y-3">
          <Step n={1} title="Create an account">
            <p>Click <b>Sign Up</b> on the login page. You only need an email, a username and a password.</p>
          </Step>
          <Step n={2} title="Explore the Overview page (home)">
            <p>Your dashboard shows open positions, recent signals, portfolio value and P&amp;L at a glance.</p>
          </Step>
          <Step n={3} title="Check the AI Signals feed">
            <p>Go to <Link href="/signals" className="text-green hover:underline">AI Signals</Link> to see current market calls from the three engines.</p>
          </Step>
          <Step n={4} title="Place your first paper trade">
            <p>Head to <Link href="/trading" className="text-green hover:underline">Trading</Link>, pick a symbol and place an order with Route set to <b>Paper</b>. No real money moves.</p>
          </Step>
          <Step n={5} title="Connect alerts">
            <p>Set up Telegram alerts under <Link href="/settings" className="text-green hover:underline">Settings</Link> so you never miss a signal (see the Telegram section below).</p>
          </Step>
        </ol>
      </Card>

      {/* Tiers */}
      <Card className="scroll-mt-20">
        <span id="tiers" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Plans &amp; Tiers</CardTitle></CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[540px]">
            <thead>
              <tr className="text-left text-text-muted text-xs uppercase tracking-wider">
                <th className="pb-2 pr-4">Plan</th>
                <th className="pb-2 pr-4">Price</th>
                <th className="pb-2">What you get</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              <tr>
                <td className="py-2.5 pr-4"><Badge variant="gray">FREE</Badge></td>
                <td className="pr-4">$0 forever</td>
                <td>Forex signals · paper trading · web notifications · signals on Telegram</td>
              </tr>
              <tr>
                <td className="pr-4"><Badge variant="blue">PREMIUM</Badge></td>
                <td className="pr-4">$49 / month</td>
                <td>+ Stock engine signals · faster API limits · full notification center</td>
              </tr>
              <tr>
                <td className="pr-4"><Badge variant="yellow">VIP</Badge></td>
                <td className="pr-4">$199 / month</td>
                <td>+ Crypto engine signals · highest rate limits · every alert category</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-text-muted mt-3">
          Your tier is shown in the sidebar. Upgrade anytime under <Link href="/billing" className="text-green hover:underline">Billing</Link>.
        </p>
      </Card>

      {/* Signals */}
      <Card className="scroll-mt-20">
        <span id="signals" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>AI Signals</CardTitle></CardHeader>
        <div className="space-y-2 text-sm text-text-secondary">
          <p>The <b>AI Signals</b> page lists every call generated by the engines:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><b>Forex engine</b> — trend-following on major pairs (all plans)</li>
            <li><b>Stock engine</b> — breakout scans during US market hours (Premium+)</li>
            <li><b>Crypto engine</b> — momentum scans, 24/7 (VIP)</li>
          </ul>
          <p>
            Each signal shows direction (buy/sell), confidence %, entry price, stop-loss and take-profit.
            Click a card for the full detail including the indicator breakdown behind the call.
            Engines scan automatically every 15 minutes; repeated calls for the same symbol are suppressed
            for 4 hours so the feed stays clean.
          </p>
          <p className="text-xs text-text-muted">
            Signals are informational, not financial advice. Always apply your own risk rules.
          </p>
        </div>
      </Card>

      {/* Trading */}
      <Card className="scroll-mt-20">
        <span id="trading" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Trading &amp; Order Routing</CardTitle></CardHeader>
        <ol className="space-y-3">
          <Step n={1} title="Choose Paper or Live">
            <p>
              On the order form, <b>Route: Paper</b> simulates the fill at the live market price — nothing hits a broker.
              <b> Route: Live</b> sends a real order through your connected broker.
            </p>
          </Step>
          <Step n={2} title="Live requires a broker connection">
            <p>
              The form tells you which venue will execute (e.g. Kraken for crypto). No connection for that market?
              You&apos;ll be prompted to connect one first.
            </p>
          </Step>
          <Step n={3} title="Market vs Limit">
            <p>Market orders fill immediately at the best price. Limit orders need a target price and rest until hit.</p>
          </Step>
          <Step n={4} title="Close positions safely">
            <p>
              Closing a live position closes it at the broker first, then records P&amp;L here. If the broker is unreachable,
              ORQEVA refuses to fake-close it — you&apos;ll see a clear error instead of silent drift between dashboards.
            </p>
          </Step>
        </ol>
      </Card>

      {/* Exchanges */}
      <Card className="scroll-mt-20">
        <span id="exchanges" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Connecting a Broker</CardTitle></CardHeader>
        <div className="space-y-2 text-sm text-text-secondary">
          <p>Under <Link href="/exchanges" className="text-green hover:underline">Exchanges</Link>, connect one broker per market:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><b>Stocks → Alpaca</b> (paper or live keys from alpaca.markets)</li>
            <li><b>Crypto → Kraken or Coinbase Advanced</b></li>
            <li><b>Forex → OANDA</b> (practice or live token)</li>
          </ul>
          <p>
            Keys are validated on connect (an invalid key is rejected immediately) and stored encrypted.
            Use each broker&apos;s <i>practice/paper</i> keys first — the connection works identically without real funds at risk.
          </p>
        </div>
      </Card>

      {/* Risk */}
      <Card className="scroll-mt-20">
        <span id="risk" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Risk Management</CardTitle></CardHeader>
        <div className="space-y-2 text-sm text-text-secondary">
          <p>The <Link href="/risk" className="text-green hover:underline">Risk Mgmt</Link> page protects your account:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><b>Kill switch</b> — one click blocks ALL new orders everywhere until you re-enable it</li>
            <li><b>Daily loss limit</b> — trading halts when losses cross your threshold</li>
            <li><b>Max open positions / daily trades</b> — hard caps enforced before every order</li>
          </ul>
          <p>Risk checks run on both paper and live routes — there is no way around them.</p>
        </div>
      </Card>

      {/* Telegram */}
      <Card className="scroll-mt-20">
        <span id="telegram" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Telegram Alerts</CardTitle></CardHeader>
        <ol className="space-y-3">
          <Step n={1} title="Open your tier's bot">
            <p>Free → @ORQEVA_free_bot · Premium → @ORQEVA_premium_bot · VIP → @ORQEVA_VIP_bot. Press <b>Start</b>.</p>
          </Step>
          <Step n={2} title="Get your chat ID">
            <p>Send any message to the bot, then message <b>@userinfobot</b> on Telegram — it replies with your numeric chat ID.</p>
          </Step>
          <Step n={3} title="Link in Settings">
            <p>Paste the ID under Settings → Telegram and press <b>Link</b>, then <b>Send Test Message</b> to confirm.</p>
          </Step>
          <Step n={4} title="Pick your categories">
            <p>Toggle signal alerts, TP/SL notifications, market analysis, risk alerts and system messages independently.</p>
          </Step>
        </ol>
        <p className="text-xs text-text-muted mt-3">
          Free tier receives signals + system messages. Premium/VIP unlock all categories.
        </p>
      </Card>

      {/* Billing */}
      <Card className="scroll-mt-20">
        <span id="billing" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>Billing &amp; Payments</CardTitle></CardHeader>
        <ol className="space-y-3">
          <Step n={1} title="Pick a plan">
            <p>On <Link href="/billing" className="text-green hover:underline">Billing</Link>, choose Premium ($49/mo) or VIP ($199/mo) and create an invoice.</p>
          </Step>
          <Step n={2} title="Pay manually">
            <p>Follow the payment instructions on the invoice (DM @Johnpaulmuna_83 for bank/card details).</p>
          </Step>
          <Step n={3} title="Submit your reference">
            <p>Enter the transaction reference from your payment on the invoice card. An admin verifies it — usually within minutes.</p>
          </Step>
          <Step n={4} title="Tier activates automatically">
            <p>Once approved, your tier upgrades instantly across the app and Telegram. Have a promo code? Apply it when creating the invoice for an instant discount.</p>
          </Step>
        </ol>
      </Card>

      {/* FAQ */}
      <Card className="scroll-mt-20">
        <span id="faq" className="block -mt-20 pt-20" aria-hidden />
        <CardHeader><CardTitle>FAQ</CardTitle></CardHeader>
        <div className="space-y-4 text-sm text-text-secondary">
          <div>
            <p className="font-medium text-text-primary">Is paper mode really free?</p>
            <p>Yes. Every plan includes unlimited-feeling paper trading with real market prices.</p>
          </div>
          <div>
            <p className="font-medium text-text-primary">Can ORQEVA withdraw my money?</p>
            <p>No. Broker connections use trade-only API keys — withdrawals are impossible by design. Never grant withdrawal permission to any third-party app.</p>
          </div>
          <div>
            <p className="font-medium text-text-primary">Why did my live order fail?</p>
            <p>The broker rejected it (insufficient balance, symbol not tradable, etc.). The exact broker message is shown — fix the cause and retry.</p>
          </div>
          <div>
            <p className="font-medium text-text-primary">How fast are signals?</p>
            <p>Engines scan every 15 minutes. Signals also arrive on Telegram within seconds of generation when linked.</p>
          </div>
          <div>
            <p className="font-medium text-text-primary">I forgot my password</p>
            <p>Contact support (@Johnpaulmuna_83) — accounts can be verified and reset manually during beta.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
