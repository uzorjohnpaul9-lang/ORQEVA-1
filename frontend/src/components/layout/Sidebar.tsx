"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useAuth } from "@/lib/auth";
import { adminNavItems, navIconMap, navItems } from "@/lib/nav";

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const items = user?.is_admin ? [...navItems, ...adminNavItems] : navItems;

  return (
    <aside className="hidden xl:flex w-64 flex-col bg-bg-secondary border-r border-border h-screen">
      <div className="flex items-center gap-3 px-6 py-5 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-green/20 flex items-center justify-center">
          <span className="text-green font-bold text-sm">O</span>
        </div>
        <span className="font-semibold text-lg tracking-wide">ORQEVA</span>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
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

      <div className="px-4 py-4 border-t border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue/20 flex items-center justify-center text-blue text-sm font-medium">
            T
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">Trader</p>
            <p className="text-xs text-text-muted truncate">Free Tier</p>
          </div>
        </div>
      </div>
    </aside>
  );
}