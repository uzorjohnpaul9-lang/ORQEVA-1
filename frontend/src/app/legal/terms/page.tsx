export const metadata = { title: "Terms of Service — ORQEVA" };

const H = ({ children }: { children: React.ReactNode }) => (
  <h2 className="text-base font-semibold mt-6 mb-2">{children}</h2>
);
const P = ({ children }: { children: React.ReactNode }) => (
  <p className="text-sm text-text-secondary leading-relaxed mb-3">{children}</p>
);

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-bg-primary">
      <div className="max-w-3xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold mb-1">Terms of Service</h1>
        <p className="text-xs text-text-muted mb-8">Last updated: August 2026 · ORQEVA (beta)</p>

        <P>By creating an ORQEVA account you agree to these terms. If you do not agree, do not use the service.</P>

        <H>1. What ORQEVA is</H>
        <P>ORQEVA is a software platform that generates AI-assisted market signals for forex, cryptocurrency and stocks, and can route orders to brokerages you connect yourself. ORQEVA is not a broker, investment adviser, or asset manager.</P>

        <H>2. Not financial advice</H>
        <P>All signals, analyses and outputs are informational only and do not constitute financial, investment, legal or tax advice. No representation is made that any signal will be profitable. Trading involves substantial risk of loss; you may lose some or all of your capital.</P>

        <H>3. Your responsibility</H>
        <P>You are solely responsible for every trading decision, every order routed through your connected broker accounts, and for the security of your API keys and password. You confirm you are at least 18 years old and legally permitted to trade in your jurisdiction.</P>

        <H>4. Broker connections</H>
        <P>ORQEVA connects to third-party brokers using trade-only API keys that you generate in your broker account. ORQEVA can never withdraw or transfer funds. You remain bound by your broker&apos;s own terms.</P>

        <H>5. Subscriptions &amp; payments</H>
        <P>Paid tiers (Premium, VIP) are billed per 30-day period as shown on the Billing page. See our Refund Policy for cancellations. We may change pricing with notice before your next renewal.</P>

        <H>6. Acceptable use</H>
        <P>No scraping, reverse engineering, sharing accounts, reselling signals, or attempting to circumvent rate limits or risk controls. Accounts violating these rules may be suspended without refund.</P>

        <H>7. Service availability</H>
        <P>The service is provided &quot;as is&quot; during beta, without warranties of any kind. We do not guarantee uninterrupted access to signals, engines, brokers or data feeds. Market data may be delayed or inaccurate.</P>

        <H>8. Limitation of liability</H>
        <P>To the maximum extent permitted by law, ORQEVA is not liable for trading losses, missed or duplicated orders, broker errors, data-feed failures, or any indirect or consequential damages. Total liability is limited to the amount you paid us in the 30 days before the claim.</P>

        <H>9. Termination</H>
        <P>You may close your account anytime. We may suspend or terminate accounts for breach of these terms.</P>

        <H>10. Changes</H>
        <P>We may update these terms; material changes will be announced in-app. Continued use after changes means acceptance.</P>

        <H>Contact</H>
        <P>Questions about these terms: DM @Johnpaulmuna_83 on Telegram.</P>
      </div>
    </div>
  );
}
