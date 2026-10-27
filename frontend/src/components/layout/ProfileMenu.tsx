"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { accountNav, adminNavItems, navIconMap, resourceNav } from "@/lib/nav";
import { tierBadgeVariant, tierLabel } from "@/lib/plans";
import { Badge } from "@/components/ui/Badge";

function MenuLink({
  href,
  label,
  icon,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: string;
  onNavigate: () => void;
}) {
  return (
    <Link
      href={href}
      role="menuitem"
      onClick={onNavigate}
      className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
    >
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d={navIconMap[icon]} />
      </svg>
      {label}
    </Link>
  );
}

export function ProfileMenu() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-bg-hover transition-colors"
      >
        <div className="w-8 h-8 rounded-full bg-blue/20 flex items-center justify-center text-blue text-sm font-medium">
          {user?.username?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || "U"}
        </div>
        <span className="text-sm hidden md:block max-w-24 truncate">{user?.username || "User"}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 w-64 max-w-[calc(100vw-1.5rem)] bg-bg-secondary border border-border rounded-xl shadow-2xl z-50 overflow-hidden"
        >
          <div className="px-4 py-3 border-b border-border">
            <p className="text-sm font-medium truncate">{user?.username || user?.email}</p>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={tierBadgeVariant(user?.tier)}>{tierLabel(user?.tier)} tier</Badge>
            </div>
          </div>

          <div className="py-1">
            {accountNav.map((item) => (
              <MenuLink key={item.href} {...item} onNavigate={() => setOpen(false)} />
            ))}
          </div>

          <div className="border-t border-border py-1">
            <p className="px-4 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Resources
            </p>
            {resourceNav.map((item) => (
              <MenuLink key={item.href} {...item} onNavigate={() => setOpen(false)} />
            ))}
            {user?.is_admin &&
              adminNavItems.map((item) => (
                <MenuLink key={item.href} {...item} onNavigate={() => setOpen(false)} />
              ))}
          </div>

          <div className="border-t border-border py-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="w-full text-left px-4 py-2.5 text-sm text-red hover:bg-bg-hover transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
