"use client";

import { useAuth } from "@/lib/auth";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";

const publicRoutes = ["/login", "/register", "/forgot", "/reset"];

function LoadingBar() {
  return (
    <div className="fixed top-0 left-0 right-0 z-50 h-0.5 overflow-hidden bg-transparent">
      <div className="h-full w-1/3 bg-green animate-[loadingbar_1.2s_ease-in-out_infinite]" />
    </div>
  );
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user && !publicRoutes.includes(pathname)) {
      router.push("/login");
      return;
    }
    if (user && pathname.startsWith("/admin") && !user.is_admin) {
      router.push("/");
    }
  }, [user, loading, pathname, router]);

  // Already signed out on a protected route: render nothing while the
  // redirect effect fires (avoids flashing a page we don't own).
  if (!loading && !user && !publicRoutes.includes(pathname)) {
    return null;
  }

  // Non-blocking: render the app shell immediately and hydrate the session in
  // the background. A slim progress bar signals the pending auth check.
  return (
    <>
      {loading && <LoadingBar />}
      {children}
    </>
  );
}
