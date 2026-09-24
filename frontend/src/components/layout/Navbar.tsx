"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

interface Notif {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export function Navbar() {
  const [showNotifs, setShowNotifs] = useState(false);
  const [showUser, setShowUser] = useState(false);
  const { user, token, logout } = useAuth();
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);

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

  async function markAll() {
    if (!token) return;
    try {
      await api("/api/notifications/read-all", { method: "POST", token });
      await load();
    } catch {}
  }

  return (
    <header className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-border bg-bg-secondary">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold hidden md:block">Dashboard</h1>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 bg-bg-tertiary rounded-lg px-3 py-2">
          <svg className="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none w-48"
          />
        </div>

        <div className="relative">
          <button onClick={() => setShowNotifs(!showNotifs)} className="relative p-2 rounded-lg hover:bg-bg-hover transition-colors">
            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />
            </svg>
            {unread > 0 && (
              <span className={`absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 bg-red rounded-full text-[10px] flex items-center justify-center text-white font-bold`}>
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </button>

          {showNotifs && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-bg-secondary border border-border rounded-xl shadow-2xl z-50">
              <div className="px-4 py-3 border-b border-border flex justify-between items-center">
                <span className="font-medium text-sm">Notifications</span>
                <button onClick={markAll} className="text-xs text-blue cursor-pointer hover:underline">Mark all read</button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifs.length === 0 ? (
                  <p className="px-4 py-6 text-xs text-text-muted text-center">No notifications yet</p>
                ) : (
                  notifs.map((n) => (
                    <div key={n.id} className={`px-4 py-3 border-b border-border/50 hover:bg-bg-hover ${!n.is_read ? "bg-blue/5" : ""}`}>
                      <p className="text-sm font-medium">{n.title}</p>
                      <p className="text-xs text-text-secondary mt-1 line-clamp-2">{n.message}</p>
                    </div>
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

        <div className="relative">
          <button onClick={() => setShowUser(!showUser)} className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-bg-hover transition-colors">
            <div className="w-8 h-8 rounded-full bg-blue/20 flex items-center justify-center text-blue text-sm font-medium">
              {user?.username?.charAt(0).toUpperCase() || "U"}
            </div>
            <span className="text-sm hidden md:block">{user?.username || "User"}</span>
          </button>

          {showUser && (
            <div className="absolute right-0 top-full mt-2 w-48 bg-bg-secondary border border-border rounded-xl shadow-2xl z-50">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-sm font-medium">{user?.username}</p>
                <p className="text-xs text-text-muted">{user?.tier} tier</p>
              </div>
              <button onClick={logout} className="w-full text-left px-4 py-3 text-sm text-red hover:bg-bg-hover rounded-b-xl">
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
