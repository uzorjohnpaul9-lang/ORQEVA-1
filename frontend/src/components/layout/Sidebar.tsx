"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useAuth } from "@/lib/auth";

const navItems = [
  { href: "/", label: "Overview", icon: "grid" },
  { href: "/signals", label: "AI Signals", icon: "zap" },
  { href: "/auto-trade", label: "Auto-Trade", icon: "sliders" },
  { href: "/trades", label: "Open Trades", icon: "trending-up" },
  { href: "/trading", label: "Trading", icon: "dollar" },
  { href: "/portfolio", label: "Portfolio", icon: "briefcase" },
  { href: "/market", label: "Market", icon: "activity" },
  { href: "/analytics", label: "Analytics", icon: "chart" },
  { href: "/risk", label: "Risk Mgmt", icon: "shield" },
  { href: "/history", label: "History", icon: "clock" },
  { href: "/billing", label: "Billing", icon: "card" },
  { href: "/ai-analysis", label: "AI Analysis", icon: "brain" },
  { href: "/exchanges", label: "Exchanges", icon: "link" },
  { href: "/notifications", label: "Notifications", icon: "bell" },
  { href: "/help", label: "Help & Guide", icon: "question" },
  { href: "/settings", label: "Settings", icon: "settings" },
  { href: "/vip", label: "VIP", icon: "crown" },
];

const adminItems = [{ href: "/admin", label: "Admin", icon: "tools" }];

const iconMap: Record<string, string> = {
  grid: "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z",
  zap: "M13 10V3L4 14h7v7l9-11h-7z",
  "trending-up": "M7 17l9.2-9.2M17 17V7.8H7.8",
  briefcase: "M20 7H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2zM16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  dollar: "M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  chart: "M18 20V10M12 20V4M6 20v-6",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  clock: "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zm0-6v-4l3 3",
  card: "M2 6a2 2 0 012-2h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm0 4h20M6 15h4",
  brain: "M12 2a7 7 0 00-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 002 2h4a2 2 0 002-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 00-7-7zm-2 18h4",
  link: "M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71",
  bell: "M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0",
  question: "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM9.09 9a3 3 0 015.83 1c0 2-3 3-3 3M12 17h.01",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z",
  crown: "M2 4l3 12h14l3-12-5 4-5-4-5 4-5-4z",
  tools: "M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z",
  sliders: "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4",
};

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const items = user?.is_admin ? [...navItems, ...adminItems] : navItems;

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
                <path strokeLinecap="round" strokeLinejoin="round" d={iconMap[item.icon]} />
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
