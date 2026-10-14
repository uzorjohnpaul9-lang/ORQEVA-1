"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/Card";
import type { CalendarActiveFeed, CalendarFeed } from "@/lib/types";

function relTime(iso: string | null | undefined, now: number): string {
  if (!iso) return "";
  const mins = Math.round((new Date(iso).getTime() - now) / 60000);
  const abs = Math.abs(mins);
  const unit =
    abs < 60
      ? `${abs}m`
      : abs < 1440
        ? `${Math.floor(abs / 60)}h ${abs % 60}m`
        : `${Math.floor(abs / 1440)}d`;
  return mins >= 0 ? `in ${unit}` : `${unit} ago`;
}

export function EventBanner() {
  const { token } = useAuth();
  const [active, setActive] = useState<CalendarActiveFeed | null>(null);
  const [next, setNext] = useState<CalendarFeed | null>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!token) return;
    api<CalendarActiveFeed>("/api/calendar/active?window_minutes=30", { token })
      .then(setActive)
      .catch(() => {});
    api<CalendarFeed>("/api/calendar/upcoming?days=3&impact=high", { token })
      .then(setNext)
      .catch(() => {});
  }, [token]);

  if (!now) return null;

  const activeEv = active?.events?.[0];
  if (active && activeEv) {
    return (
      <Card className="border-red/40">
        <div className="flex items-start gap-3">
          <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-red shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-red">High-impact event window</p>
            <p className="text-sm text-text-secondary mt-0.5">
              {active.events.map((e) => e.name).join(", ")} — {relTime(activeEv.time_utc, now)}
              {active.affected_markets.length > 0 &&
                ` · may affect ${active.affected_markets.join(", ")}`}
            </p>
            <Link
              href="/calendar"
              className="text-xs text-text-muted hover:text-text-primary mt-1 inline-block"
            >
              View calendar →
            </Link>
          </div>
        </div>
      </Card>
    );
  }

  const upcoming = next?.events?.filter(
    (e) => e.time_utc && new Date(e.time_utc).getTime() > now
  )[0];
  if (!upcoming) return null;

  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="h-2.5 w-2.5 rounded-full bg-blue shrink-0" />
          <p className="text-sm text-text-secondary">
            Next high-impact:{" "}
            <span className="font-medium text-text-primary">{upcoming.name}</span>{" "}
            <span className="text-text-muted">{relTime(upcoming.time_utc, now)}</span>
          </p>
        </div>
        <Link href="/calendar" className="text-xs text-text-muted hover:text-text-primary whitespace-nowrap">
          Calendar →
        </Link>
      </div>
    </Card>
  );
}
