"use client";

import { useEffect, useRef } from "react";
import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { Sidebar } from "@/components/layout/Sidebar";
import { Navbar } from "@/components/layout/Navbar";
import { MobileNav } from "@/components/layout/MobileNav";
import { SignalsFeedProvider } from "@/lib/signalsFeed";
import { usePathname } from "next/navigation";

const publicRoutes = ["/login", "/register", "/forgot", "/reset", "/support"];
const legalRoutes = ["/legal/terms", "/legal/privacy", "/legal/refunds"];

/**
 * Fades a page in on route change WITHOUT remounting its subtree.
 *
 * A `key={pathname}` wrapper would remount every page â€” re-running effects,
 * refetching and re-initialising charts. We instead retrigger an opacity-only
 * animation (no transform, so it never becomes a containing block for the
 * fixed-position modals portaled to <body>).
 */
function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.classList.remove("animate-fade-in");
    void el.offsetWidth; // force reflow so the animation restarts
    el.classList.add("animate-fade-in");
  }, [pathname]);

  return <div ref={ref} className="animate-fade-in">{children}</div>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = publicRoutes.includes(pathname) || legalRoutes.some((r) => pathname.startsWith(r));

  return (
    <AuthProvider>
      <AuthGuard>
        {isPublic ? (
          <div className="min-h-dvh flex flex-col">
            <PageTransition><div className="flex-1">{children}</div></PageTransition>
            <DisclaimerFooter />
          </div>
        ) : (
          <SignalsFeedProvider>
            <div className="flex h-dvh overflow-hidden">
              <Sidebar />
              <div className="flex flex-1 flex-col overflow-hidden">
                <Navbar />
                <main className="flex-1 overflow-y-auto p-4 pb-20 xl:pb-6">
                  <PageTransition>{children}</PageTransition>
                  <DisclaimerFooter inApp />
                </main>
              </div>
              <MobileNav />
            </div>
          </SignalsFeedProvider>
        )}
      </AuthGuard>
    </AuthProvider>
  );
}

function DisclaimerFooter({ inApp = false }: { inApp?: boolean }) {
  return (
    <footer className={inApp ? "mt-8 pt-4 border-t border-border/50" : "px-4 py-4 text-center bg-bg-secondary border-t border-border"}>
      <p className={`text-xs text-text-muted ${inApp ? "" : "max-w-3xl mx-auto"}`}>
        ORQEVA provides AI-generated market signals and trading tools for informational purposes only.
        Nothing here is financial advice. Trading involves substantial risk of loss â€” never trade with money you cannot afford to lose.{" "}
        <a href="/legal/terms" className="underline hover:text-text-secondary">Terms</a> Â·{" "}
        <a href="/legal/privacy" className="underline hover:text-text-secondary">Privacy</a> Â·{" "}
        <a href="/legal/refunds" className="underline hover:text-text-secondary">Refunds</a>
      </p>
    </footer>
  );
}
