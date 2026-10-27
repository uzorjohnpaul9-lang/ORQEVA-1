"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { getRouteMeta } from "@/lib/nav";
import { NotificationSheet, type Notif } from "@/components/ui/NotificationSheet";
import { ProfileMenu } from "@/components/layout/ProfileMenu";

export function Navbar() {
  const pathname = usePathname();
  const meta = getRouteMeta(pathname);
  const [showNotifs, setShowNotifs] = useState(false);
  const { token } = useAuth();
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);
  const [detail, setDetail] = useState<Notif | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const body = await api<{ notifications: Notif[]; unread_count: number }>(
        "/api/notifications?limit=5", { token });
      setNotifs(body.notifications);
      setUnread(body.unread_count);
    } catch {}
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  useEffect(() => {
    setShowNotifs(false);
  }, [pathname]);

  async function markAll() {
    if (!token) return;
    try {
      await api("/api/notifications/read-all", { method: "POST", token });
      await load();
    } catch {}
  }

  return (
    <header className="flex h-14 items-center justify-between gap-3 px-4 md:px-6 border-b border-border bg-bg-secondary">
      <div className="flex min-w-0 items-center gap-2">
        {meta.section && (
          <span className="hidden sm:inline text-xs text-text-muted shrink-0">{meta.section} /</span>
        )}
        <h1 className="truncate text-base font-semibold">{meta.title}</h1>
      </div>

      <div className="flex items-center gap-1.5">
        <Link
          href="/trading"
          data-tour="trading"
          className="lg:hidden inline-flex items-center gap-1.5 rounded-lg bg-green px-3 py-2 text-xs font-semibold text-bg-primary hover:bg-green/90 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" />
          </svg>
          Trade
        </Link>

        <div className="relative">
          <button
            type="button"
            onClick={() => setShowNotifs(!showNotifs)}
            aria-label="Notifications"
            aria-expanded={showNotifs}
            className="relative p-2 rounded-lg hover:bg-bg-hover transition-colors"
          >
            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />
            </svg>
            {unread > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 bg-red rounded-full text-[10px] flex items-center justify-center text-white font-bold">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </button>

          {showNotifs && (
            <div className="absolute right-0 top-full mt-2 w-80 max-w-[calc(100vw-1.5rem)] bg-bg-secondary border border-border rounded-xl shadow-2xl z-50">
              <div className="px-4 py-3 border-b border-border flex justify-between items-center">
                <span className="font-medium text-sm">Notifications</span>
                <button onClick={markAll} className="text-xs text-blue cursor-pointer hover:underline">Mark all read</button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifs.length === 0 ? (
                  <p className="px-4 py-6 text-xs text-text-muted text-center">No notifications yet</p>
                ) : (
                  notifs.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        setShowNotifs(false);
                        setDetail(n);
                        if (!n.is_read && token) {
                          api("/api/notifications/read", { method: "POST", token, body: { notification_id: n.id } }).then(load).catch(() => {});
                        }
                      }}
                      className={`w-full text-left px-4 py-3 border-b border-border/50 hover:bg-bg-hover ${!n.is_read ? "bg-blue/5" : ""}`}
                    >
                      <p className="text-sm font-medium">{n.title}</p>
                      <p className="text-xs text-text-secondary mt-1 line-clamp-2">{n.message}</p>
                    </button>
                  ))
                )}
              </div>
              <Link href="/notifications" onClick={() => setShowNotifs(false)}
                className="block px-4 py-2.5 text-xs text-blue hover:bg-bg-hover rounded-b-xl">
                View all
              </Link>
            </div>
          )}
        </div>

        <ProfileMenu />
      </div>

      <NotificationSheet notif={detail} onClose={() => setDetail(null)} token={token} />
    </header>
  );
}
