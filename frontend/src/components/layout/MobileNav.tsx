"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useAuth } from "@/lib/auth";
import { Modal } from "@/components/ui/Modal";
import { adminNavItems, navIconMap, navItems } from "@/lib/nav";

const tabs = [
  { href: "/", label: "Home", icon: "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" },
  { href: "/signals", label: "Signals", icon: "M13 10V3L4 14h7v7l9-11h-7z" },
  { href: "/trades", label: "Trades", icon: "M7 17l9.2-9.2M17 17V7.8H7.8" },
  { href: "/market", label: "Market", icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/settings", label: "More", icon: "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4" },
];

export function MobileNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const prevPathname = useRef(pathname);
  useEffect(() => {
    if (prevPathname.current !== pathname && menuOpen) setMenuOpen(false);
    prevPathname.current = pathname;
  }, [pathname, menuOpen]);

  const menuItems = user?.is_admin ? [...navItems, ...adminNavItems] : navItems;

  return (
    <>
      <nav className="xl:hidden fixed bottom-0 left-0 right-0 bg-bg-secondary border-t border-border z-50">
        <div className="flex items-center justify-around py-2">
          {tabs.map((tab) => {
            const active = pathname === tab.href;
            const isMore = tab.label === "More";
return (
              <button
                key={tab.href}
                onClick={isMore ? () => setMenuOpen(true) : () => router.push(tab.href)}
                className={clsx(
                  "flex flex-col items-center gap-1 px-3 py-1.5 rounded-lg min-w-[60px] transition-colors cursor-pointer",
                  active ? "text-green" : "text-text-muted"
                )}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={tab.icon} />
                </svg>
                <span className="text-[10px]">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      <Modal open={menuOpen} onClose={() => setMenuOpen(false)} title="All Sections" align="bottom">
        <div className="grid grid-cols-3 gap-2">
          {menuItems.map((item) => {
            const active = pathname === item.href;
            return (
              <button
                key={item.href}
                onClick={() => {
                  setMenuOpen(false);
                  router.push(item.href);
                }}
                className={clsx(
                  "flex flex-col items-center gap-2 p-3 rounded-xl border transition-colors text-center",
                  active
                    ? "border-green/40 bg-green/10 text-green"
                    : "border-border bg-bg-tertiary text-text-secondary hover:bg-bg-hover hover:text-text-primary"
                )}
              >
                <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[item.icon]} />
                </svg>
                <span className="text-xs leading-tight">{item.label}</span>
              </button>
            );
          })}
        </div>
      </Modal>
    </>
  );
}