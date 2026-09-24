export const metadata = { title: "Privacy Policy — ORQEVA" };

const H = ({ children }: { children: React.ReactNode }) => (
  <h2 className="text-base font-semibold mt-6 mb-2">{children}</h2>
);
const P = ({ children }: { children: React.ReactNode }) => (
  <p className="text-sm text-text-secondary leading-relaxed mb-3">{children}</p>
);

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-bg-primary">
      <div className="max-w-3xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold mb-1">Privacy Policy</h1>
        <p className="text-xs text-text-muted mb-8">Last updated: August 2026 · ORQEVA (beta)</p>

        <H>What we collect</H>
        <P>
          Account data (email, username, hashed password), your subscription tier and invoices,
          trading records created in the app, connected broker API keys (stored encrypted),
          Telegram chat ID if you link alerts, and basic usage needed to run the service.
        </P>

        <H>What we never collect</H>
        <P>
          We never see or store your broker account passwords, and we cannot move funds —
          connections use trade-only API keys with no withdrawal permission.
        </P>

        <H>How data is used</H>
        <P>
          To operate your account (authentication, signals, order routing, notifications),
          to process subscriptions, and to keep the platform secure (rate limiting, abuse prevention).
          We do not sell your personal data.
        </P>

        <H>Data sharing</H>
        <P>
          Data is shared only with processors strictly required to run the service:
          our hosting provider, our database, Telegram (when you opt into alerts), and your own
          broker when you route orders. Payment details are handled manually during beta.
        </P>

        <H>Password &amp; key security</H>
        <P>
          Passwords are stored as bcrypt hashes. Broker API keys are encrypted at rest.
          Password reset links are single-use and expire after 30 minutes.
        </P>

        <H>Your rights (GDPR-style)</H>
        <P>
          You can request a copy of your data or deletion of your account at any time by
          contacting support. Deletion removes your profile, trades, notifications and
          preferences; aggregated anonymous statistics may be retained.
        </P>

        <H>Cookies &amp; local storage</H>
        <P>
          We use browser local storage to keep you signed in. No advertising or third-party
          tracking cookies are used.
        </P>

        <H>Contact</H>
        <P>Privacy requests: DM @Johnpaulmuna_83 on Telegram.</P>
      </div>
    </div>
  );
}
