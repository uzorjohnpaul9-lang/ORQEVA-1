"use client";

import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { Sidebar } from "@/components/layout/Sidebar";
import { Navbar } from "@/components/layout/Navbar";
import { MobileNav } from "@/components/layout/MobileNav";
import { usePathname } from "next/navigation";

const publicRoutes = ["/login", "/register", "/forgot", "/reset"];
const legalRoutes = ["/legal/terms", "/legal/privacy", "/legal/refunds"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = publicRoutes.includes(pathname) || legalRoutes.some((r) => pathname.startsWith(r));

  return (
    <AuthProvider>
      <AuthGuard>
        {isPublic ? (
          <div className="min-h-screen flex flex-col">
            <div className="flex-1">{children}</div>
            <DisclaimerFooter />
          </div>
        ) : (
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <div className="flex flex-1 flex-col overflow-hidden">
              <Navbar />
              <main className="flex-1 overflow-y-auto p-4 md:p-6 pb-20 md:pb-6">
                {children}
                <DisclaimerFooter inApp />
              </main>
            </div>
            <MobileNav />
          </div>
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
        Nothing here is financial advice. Trading involves substantial risk of loss — never trade with money you cannot afford to lose.{" "}
        <a href="/legal/terms" className="underline hover:text-text-secondary">Terms</a> ·{" "}
        <a href="/legal/privacy" className="underline hover:text-text-secondary">Privacy</a> ·{" "}
        <a href="/legal/refunds" className="underline hover:text-text-secondary">Refunds</a>
      </p>
    </footer>
  );
}
