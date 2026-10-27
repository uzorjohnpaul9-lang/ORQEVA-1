"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clsx } from "clsx";
import { useAuth } from "@/lib/auth";
import { Modal } from "@/components/ui/Modal";
import {
  adminNavItems,
  isNavActive,
  mobileTabs,
  moreGroups,
  navIconMap,
  type NavGroup,
} from "@/lib/nav";

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

  const groups: NavGroup[] = user?.is_admin
    ? [...moreGroups, { label: "Admin", items: adminNavItems }]
    : moreGroups;

  const moreActive =
    groups.some((group) => group.items.some((item) => isNavActive(pathname, item.href))) ||
    isNavActive(pathname, "/trading/automation");

  return (
    <>
      <nav
        className="lg:hidden fixed bottom-0 left-0 right-0 bg-bg-secondary border-t border-border z-50"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        aria-label="Primary"
      >
        <div className="flex items-center justify-around py-2">
          {mobileTabs.map((tab) => {
            const isMore = tab.href === "__more";
            const active = isMore ? moreActive : isNavActive(pathname, tab.href);
            return (
              <button
                key={tab.href}
                type="button"
                data-tour={tab.tour}
                aria-current={active ? "page" : undefined}
                onClick={() => {
                  if (isMore) setMenuOpen(true);
                  else router.push(tab.href);
                }}
                className={clsx(
                  "flex flex-col items-center gap-1 px-3 py-1.5 rounded-lg min-w-[60px] transition-colors cursor-pointer",
                  active ? "text-green" : "text-text-muted"
                )}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[tab.icon]} />
                </svg>
                <span className="text-[10px]">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      <Modal open={menuOpen} onClose={() => setMenuOpen(false)} title="More" align="bottom">
        <div className="space-y-5 pb-2">
          {groups.map((group) => (
            <div key={group.label}>
              <p className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                {group.label}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = isNavActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMenuOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={clsx(
                        "flex items-center gap-3 rounded-xl border px-3 py-3 text-sm transition-colors",
                        active
                          ? "border-green/40 bg-green/10 text-green"
                          : "border-border bg-bg-tertiary text-text-secondary hover:bg-bg-hover hover:text-text-primary"
                      )}
                    >
                      <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[item.icon]} />
                      </svg>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}
