export const metadata = { title: "Refund Policy — ORQEVA" };

const H = ({ children }: { children: React.ReactNode }) => (
  <h2 className="text-base font-semibold mt-6 mb-2">{children}</h2>
);
const P = ({ children }: { children: React.ReactNode }) => (
  <p className="text-sm text-text-secondary leading-relaxed mb-3">{children}</p>
);

export default function RefundPage() {
  return (
    <div className="min-h-screen bg-bg-primary">
      <div className="max-w-3xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold mb-1">Refund Policy</h1>
        <p className="text-xs text-text-muted mb-8">Last updated: August 2026 · ORQEVA (beta)</p>

        <H>7-day beta guarantee</H>
        <P>
          If a paid subscription (Premium or VIP) doesn&apos;t work as described, contact us within
          7 days of payment for a full refund. We&apos;d rather fix the problem than keep your money.
        </P>

        <H>After the first week</H>
        <P>
          Refunds past 7 days are handled case-by-case — e.g. extended outages on our side, or
          accidental double payments (always refunded in full). Signal performance alone is not a
          refund reason: markets involve risk and past results never guarantee future ones.
        </P>

        <H>How to request</H>
        <P>
          DM @Johnpaulmuna_83 on Telegram with your account email and transaction reference.
          Approved refunds return to the original payment method within 5–10 business days.
        </P>

        <H>Non-refundable</H>
        <P>
          Accounts terminated for abuse (shared logins, reselling signals, attacking the platform)
          forfeit refunds. Partial months at cancellation are not prorated unless covered above.
        </P>
      </div>
    </div>
  );
}
