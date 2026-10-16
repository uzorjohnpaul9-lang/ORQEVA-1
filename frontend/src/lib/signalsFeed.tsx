"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Signal } from "@/lib/types";

interface FeedState {
  /** True while the SSE connection is open. */
  live: boolean;
  /** Signals pushed over SSE this session (newest first). Consumers dedupe. */
  incoming: Signal[];
}

const SignalsFeedContext = createContext<FeedState>({ live: false, incoming: [] });

const MAX_BUFFER = 200;

/**
 * Single, app-wide SSE connection to /api/signals/feed.
 *
 * Lives in the shell so the socket connects once and survives client-side
 * navigation between pages, instead of reconnecting on every page mount.
 */
export function SignalsFeedProvider({ children }: { children: ReactNode }) {
  const { token, user } = useAuth();
  const [live, setLive] = useState(false);
  const [incoming, setIncoming] = useState<Signal[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!token || !user) return;
    const url = `${API_BASE}/api/signals/feed?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("signal", (ev) => {
      try {
        const s: Signal = JSON.parse((ev as MessageEvent).data);
        setIncoming((prev) => (prev.some((p) => p.id === s.id) ? prev : [s, ...prev].slice(0, MAX_BUFFER)));
      } catch {
        /* ignore malformed frames */
      }
    });
    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);

    return () => {
      es.close();
      esRef.current = null;
      setLive(false);
      setIncoming([]);
    };
  }, [token, user]);

  return (
    <SignalsFeedContext.Provider value={{ live, incoming }}>
      {children}
    </SignalsFeedContext.Provider>
  );
}

export function useSignalsFeed(): FeedState {
  return useContext(SignalsFeedContext);
}
