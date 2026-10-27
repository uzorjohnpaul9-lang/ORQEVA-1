"use client";

import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { Sidebar } from "@/components/layout/Sidebar";
import { Navbar } from "@/components/layout/Navbar";
import { MobileNav } from "@/components/layout/MobileNav";
import { DisclaimerFooter } from "@/components/layout/DisclaimerFooter";
import { PageTransition } from "@/components/layout/PageTransition";
import { SignalsFeedProvider } from "@/lib/signalsFeed";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGuard>
        <SignalsFeedProvider>
          <div className="flex h-dvh overflow-hidden">
            <Sidebar />
            <div className="flex flex-1 flex-col overflow-hidden">
              <Navbar />
              <main className="flex-1 overflow-y-auto p-4 pb-6">
                <PageTransition>{children}</PageTransition>
                <DisclaimerFooter inApp />
              </main>
            </div>
            <MobileNav />
          </div>
        </SignalsFeedProvider>
      </AuthGuard>
    </AuthProvider>
  );
}
