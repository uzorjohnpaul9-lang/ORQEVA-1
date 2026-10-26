"use client";

import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { DisclaimerFooter } from "@/components/layout/DisclaimerFooter";
import { PageTransition } from "@/components/layout/PageTransition";

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGuard>
        <div className="min-h-dvh flex flex-col">
          <PageTransition><div className="flex-1">{children}</div></PageTransition>
          <DisclaimerFooter />
        </div>
      </AuthGuard>
    </AuthProvider>
  );
}
