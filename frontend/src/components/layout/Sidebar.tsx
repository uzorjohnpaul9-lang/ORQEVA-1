"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { isNavActive, navIconMap, primaryNav } from "@/lib/nav";
import { SignalPulse } from "@/components/ui/SignalPulse";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex w-60 flex-col bg-bg-secondary border-r border-border h-dvh">
      <Link href="/dashboard" className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <SignalPulse size={34} rings={2}>
          <span className="text-[10px] font-bold">O</span>
        </SignalPulse>
        <span className="font-semibold text-lg tracking-wide">ORQEVA</span>
      </Link>

      <nav className="flex-1 overflow-y-auto py-4 px-3" aria-label="Primary">
        {primaryNav.map((item) => {
          const active = isNavActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              data-tour={item.tour}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-1 transition-colors",
                active
                  ? "bg-green/10 text-green"
                  : "text-text-secondary hover:bg-bg-hover hover:text-text-primary"
              )}
            >
              <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[item.icon]} />
              </svg>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-border">
        <p className="text-xs text-text-muted">Paper-first execution</p>
        <p className="text-[11px] text-text-muted/70 mt-0.5">Illustrative. Not financial advice.</p>
      </div>
    </aside>
  );
}
