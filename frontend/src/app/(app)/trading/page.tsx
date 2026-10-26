import { Suspense } from "react";
import TradingPage from "./page_inner";

export default function Page() {
  return (
    <Suspense
      fallback={<p className="text-sm text-text-muted">Loading trading terminal…</p>}
    >
      <TradingPage />
    </Suspense>
  );
}
