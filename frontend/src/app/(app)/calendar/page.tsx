"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { CalendarActiveFeed, CalendarAttribution, CalendarEvent, CalendarFeed } from "@/lib/types";

const IMPACTS = ["all", "high", "medium"] as const;
const DAY_RANGES = [1, 7, 30] as const;

const IMPACT_VARIANT: Record<string, "red" | "yellow" | "gray"> = {
  high: "red",
  medium: "yellow",
  low: "gray",
};

function fmtTime(ev: CalendarEvent): string {
  if (ev.all_day || !ev.time_utc) return "All day";
  return new Date(ev.time_utc).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function CalendarPage() {
  const { token } = useAuth();
  const [days, setDays] = useState<number>(7);
  const [impact, setImpact] = useState<(typeof IMPACTS)[number]>("all");
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [active, setActive] = useState<CalendarActiveFeed | null>(null);
  const [attribution, setAttribution] = useState<CalendarAttribution | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    const qs = `?days=${days}${impact !== "all" ? `&impact=${impact}` : ""}`;
    api<CalendarFeed>(`/api/calendar/upcoming${qs}`, { token })
      .then((d) => {
        setEvents(d.events);
        setAttribution(d.attribution);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, days, impact]);

  useEffect(() => {
    if (!token) return;
    api<CalendarActiveFeed>("/api/calendar/active?window_minutes=30", { token })
      .then(setActive)
      .catch(() => {});
  }, [token]);

  const activeEv = active?.events?.[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Economic Calendar</h1>
        <span className="text-xs text-text-muted">
          Scheduled events that may move the markets
        </span>
      </div>

      {active && activeEv && (
        <Card className="border-red/40">
          <div className="flex items-start gap-3">
            <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-red shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red">
                High-impact event in the next {active.events[0]?.minutes_away ?? 30} min
              </p>
              <p className="text-sm text-text-secondary mt-0.5">
                {active.events.map((e) => e.name).join(", ")}
                {active.affected_markets.length > 0 &&
                  ` · may affect ${active.affected_markets.join(", ")}`}
              </p>
            </div>
          </div>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {DAY_RANGES.map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              days === d ? "bg-green text-black" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
            }`}
          >
            {d === 1 ? "Today" : `${d} days`}
          </button>
        ))}
        <span className="w-px h-5 bg-border mx-1" />
        {IMPACTS.map((imp) => (
          <button
            key={imp}
            onClick={() => setImpact(imp)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              impact === imp ? "bg-blue text-white" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
            }`}
          >
            {imp.toUpperCase()}
          </button>
        ))}
        <span className="ml-auto text-xs text-text-muted">{events.length} events</span>
      </div>

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs text-text-muted py-2 px-5">When</th>
                <th className="text-left text-xs text-text-muted py-2">Event</th>
                <th className="text-left text-xs text-text-muted py-2">Impact</th>
                <th className="text-left text-xs text-text-muted py-2">May affect</th>
                <th className="text-right text-xs text-text-muted py-2 px-5"></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-text-muted">
                    Loading events…
                  </td>
                </tr>
              )}
              {!loading && events.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-text-muted">
                    No scheduled events in this range.
                  </td>
                </tr>
              )}
              {!loading &&
                events.map((ev, i) => (
                  <tr key={`${ev.name}-${ev.time_utc}-${i}`} className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 px-5 whitespace-nowrap text-text-secondary">{fmtTime(ev)}</td>
                    <td className="py-2.5 font-medium">{ev.name}</td>
                    <td className="py-2.5">
                      <Badge variant={IMPACT_VARIANT[ev.impact] ?? "gray"}>{ev.impact}</Badge>
                    </td>
                    <td className="py-2.5 text-text-secondary capitalize">
                      {ev.affected_markets.join(", ") || "—"}
                    </td>
                    <td className="py-2.5 px-5 text-right">
                      {ev.url && (
                        <a
                          href={ev.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="text-xs text-blue hover:underline"
                        >
                          Details
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Card>

      {(attribution || active?.attribution) && (
        <p className="text-xs text-text-muted">
          Event data from{" "}
          <a
            href={(attribution ?? active?.attribution)?.url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-blue hover:underline"
          >
            {(attribution ?? active?.attribution)?.source}
          </a>
          . Events may affect price action; this is not financial advice.
        </p>
      )}
    </div>
  );
}
