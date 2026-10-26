export function DisclaimerFooter({ inApp = false }: { inApp?: boolean }) {
  return (
    <footer className={inApp ? "mt-8 pt-4 border-t border-border/50" : "px-4 py-4 text-center bg-bg-secondary border-t border-border"}>
      <p className={`text-xs text-text-muted ${inApp ? "" : "max-w-3xl mx-auto"}`}>
        ORQEVA provides AI-generated market signals and trading tools for informational purposes only.
        Nothing here is financial advice. Trading involves substantial risk of loss - never trade with money you cannot afford to lose.{" "}
        <a href="/legal/terms" className="underline hover:text-text-secondary">Terms</a>{" "}
        <a href="/legal/privacy" className="underline hover:text-text-secondary">Privacy</a>{" "}
        <a href="/legal/refunds" className="underline hover:text-text-secondary">Refunds</a>
      </p>
    </footer>
  );
}
