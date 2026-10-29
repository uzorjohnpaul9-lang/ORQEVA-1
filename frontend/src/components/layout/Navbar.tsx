"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { adminNavItems, getRouteMeta, isNavActive, moreGroups, navIconMap, primaryNav, resourceNav } from "@/lib/nav";
import { ProfileMenu } from "@/components/layout/ProfileMenu";
import { clsx } from "clsx";

export function Navbar() {
  const pathname = usePathname();
  const meta = getRouteMeta(pathname);
  const [navOpen, setNavOpen] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  const groups = user?.is_admin
    ? [...moreGroups, { label: "Admin", items: adminNavItems }]
    : moreGroups;

  return (
    <>
      <header className="flex h-14 items-center justify-between gap-2 px-3 md:px-6 border-b border-border bg-bg-secondary">
        <div className="flex min-w-0 items-center gap-2">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={navOpen}
            data-tour="nav-hamburger"
            className="lg:hidden p-2 rounded-lg hover:bg-bg-hover transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap.menu} />
            </svg>
          </button>
          {meta.section && (
            <span className="hidden sm:inline text-xs text-text-muted shrink-0">{meta.section} /</span>
          )}
          <h1 className="truncate text-base font-semibold">{meta.title}</h1>
        </div>

        <div className="flex items-center gap-1.5">
          <Link
            href="/trading"
            data-tour="trading"
            className="inline-flex items-center gap-1.5 rounded-lg bg-green px-3 py-1.5 text-xs font-semibold text-bg-primary hover:bg-green/90 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" />
            </svg>
            Trade
          </Link>

          <Link
            href="/"
            aria-label="Home"
            title="Home"
            className="p-2 rounded-lg hover:bg-bg-hover transition-colors"
          >
            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 9.5 12 3l9 6.5V21a1 1 0 01-1 1h-5v-7H9v7H4a1 1 0 01-1-1V9.5z" />
            </svg>
          </Link>

          <ProfileMenu />
        </div>
      </header>

      <div className="lg:hidden border-b border-border bg-bg-secondary">
        <div className="flex items-center gap-2 overflow-x-auto px-3 py-2 no-scrollbar">
          {primaryNav.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.tour}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors",
                  active ? "bg-green text-bg-primary" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>

      {navOpen && (
        <div className="fixed inset-0 z-[60] lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setNavOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-[85%] max-w-sm bg-bg-primary border-r border-border flex flex-col">
            <div className="flex items-center justify-between px-4 h-14 border-b border-border">
              <span className="text-sm font-semibold">Menu</span>
              <button
                type="button"
                onClick={() => setNavOpen(false)}
                aria-label="Close navigation menu"
                className="p-2 rounded-lg hover:bg-bg-hover transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
              {groups.map((group) => (
                <div key={group.label}>
                  <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                    {group.label}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((item) => {
                      const active = isNavActive(pathname, item.href);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setNavOpen(false)}
                          aria-current={active ? "page" : undefined}
                          className={clsx(
                            "flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm transition-colors",
                            active ? "bg-green/10 text-green" : "text-text-secondary hover:bg-bg-hover hover:text-text-primary"
                          )}
                        >
                          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[item.icon]} />
                          </svg>
                          {item.label}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}
              <div>
                <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Resources
                </p>
                <div className="space-y-1">
                  {resourceNav.map((item) => {
                    const active = isNavActive(pathname, item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setNavOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className={clsx(
                          "flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm transition-colors",
                          active ? "bg-green/10 text-green" : "text-text-secondary hover:bg-bg-hover hover:text-text-primary"
                        )}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[item.icon]} />
                        </svg>
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

    </>
  );
}
