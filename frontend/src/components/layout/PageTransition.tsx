"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

/**
 * Fades a page in on route change WITHOUT remounting its subtree.
 *
 * A `key={pathname}` wrapper would remount every page - re-running effects,
 * refetching and re-initialising charts. We instead retrigger an opacity-only
 * animation (no transform, so it never becomes a containing block for the
 * fixed-position modals portaled to <body>).
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.classList.remove("animate-fade-in");
    void el.offsetWidth;
    el.classList.add("animate-fade-in");
  }, [pathname]);

  return <div ref={ref} className="animate-fade-in">{children}</div>;
}
