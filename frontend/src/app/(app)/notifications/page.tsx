"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { NotificationSheet, type Notif } from "@/components/ui/NotificationSheet";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const typeColors: Record<string, "green" | "red" | "blue" | "yellow" | "purple" | "gray"> = {
  signal: "green", tp: "green", sl: "red", risk: "yellow",
  system: "gray", trade: "blue", trade_warning: "yellow",
};

export default function NotificationsPage() {
  const { token } = useAuth();
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Notif | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const q = filter === "unread" ? "?unread_only=true" : "";
      const body = await api<{ notifications: Notif[]; unread_count: number }>(
        `/api/notifications${q}`, { token });
      setNotifs(body.notifications);
      setUnread(body.unread_count);
    } catch {}
    setLoading(false);
  }, [token, filter]);

  useEffect(() => { refresh(); }, [refresh]);

  async function markRead(id: string) {
    if (!token) return;
    try {
      await api("/api/notifications/read", { method: "POST", token, body: { notification_id: id } });
      setNotifs((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      setUnread((u) => Math.max(0, u - 1));
    } catch {}
  }

  async function markAll() {
    if (!token) return;
    try {
      await api("/api/notifications/read-all", { method: "POST", token });
      await refresh();
    } catch {}
  }

  async function clearRead() {
    if (!token) return;
    try {
      await api("/api/notifications/read", { method: "DELETE", token });
      await refresh();
    } catch {}
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold">
          Notifications {unread > 0 && <span className="text-sm font-normal text-text-secondary">({unread} unread)</span>}
        </h1>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={markAll} disabled={unread === 0}>Mark all read</Button>
          <Button variant="danger" size="sm" onClick={clearRead}>Clear read</Button>
        </div>
      </div>

      <div className="flex gap-2">
        {(["all", "unread"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-lg text-sm transition-colors ${filter === f ? "bg-blue text-white" : "bg-bg-tertiary text-text-secondary hover:bg-bg-hover"}`}
          >
            {f === "all" ? "All" : `Unread${unread ? ` (${unread})` : ""}`}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-text-muted">Loading notifications...</p>
      ) : notifs.length === 0 ? (
        <Card><p className="text-sm text-text-muted py-8 text-center">You&apos;re all caught up.</p></Card>
      ) : (
        <div className="space-y-2">
          {notifs.map((n) => (
            <Card
              key={n.id}
              className={`cursor-pointer transition-colors hover:bg-bg-hover ${!n.is_read ? "border-blue/30 bg-blue/5" : ""}`}
            >
              <div
                className="flex items-start gap-3"
                onClick={() => {
                  setDetail(n);
                  if (!n.is_read) markRead(n.id);
                }}
              >
                <Badge variant={typeColors[n.type] || "gray"}>{n.type}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="text-xs text-text-secondary mt-1 break-words">{n.message}</p>
                  <p className="text-xs text-text-muted mt-2">{new Date(n.created_at).toLocaleString()}</p>
                </div>
                {!n.is_read && <span className="w-2 h-2 rounded-full bg-blue mt-2 shrink-0" />}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Link href="/settings" className="inline-block text-xs text-text-secondary hover:text-text-primary hover:underline">
        Manage Telegram delivery in Settings →
      </Link>

      <NotificationSheet notif={detail} onClose={() => setDetail(null)} token={token} />
    </div>
  );
}
