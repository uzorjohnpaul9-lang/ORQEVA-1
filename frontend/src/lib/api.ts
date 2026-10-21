export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";

export interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  /** Abort the request after this many ms (default 20000). */
  timeoutMs?: number;
  /** Cache GET responses for this many ms (default 15000, 0 disables). */
  cacheTtlMs?: number;
  /** Force a network fetch, bypassing cache. */
  noCache?: boolean;
}

interface CacheEntry {
  expires: number;
  staleUntil: number;
  value: unknown;
}

const DEFAULT_TTL = 15000;
const DEFAULT_TIMEOUT = 20000;
// After a cache entry expires we still serve it instantly for this long while
// a fresh copy is fetched in the background (stale-while-revalidate).
const STALE_WINDOW = 5 * 60_000;

const _cache = new Map<string, CacheEntry>();
const _inflight = new Map<string, Promise<unknown>>();
const _revalidating = new Set<string>();

function getTokenKey(token?: string): string {
  return token ? token.slice(-12) : "anon";
}

function setCache(key: string, value: unknown, ttl: number): void {
  const now = Date.now();
  _cache.set(key, { expires: now + ttl, staleUntil: now + ttl + STALE_WINDOW, value });
}

/** Clear cached GET responses (all, or those whose key contains `match`). */
export function clearApiCache(match?: string): void {
  if (!match) {
    _cache.clear();
    return;
  }
  for (const key of Array.from(_cache.keys())) {
    if (key.includes(match)) _cache.delete(key);
  }
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const method = opts.method || (opts.body ? "POST" : "GET");
  const isGet = method === "GET" || method === "HEAD";
  const key = `${method}:${path}:${getTokenKey(opts.token)}`;
  const ttl = opts.cacheTtlMs ?? DEFAULT_TTL;

  const headers: Record<string, string> = {};
  if (opts.body) headers["Content-Type"] = "application/json";
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;

  if (isGet && !opts.noCache) {
    const hit = _cache.get(key);
    if (hit) {
      if (hit.expires > Date.now()) {
        return hit.value as T;
      }
      if (hit.staleUntil > Date.now()) {
        // Serve the stale value instantly; refresh the cache in the background
        // so the next visit/route is fresh without ever blocking the UI.
        if (!_revalidating.has(key)) {
          _revalidating.add(key);
          fetchWithTimeout(`${API_BASE}${path}`, { method, headers }, opts.timeoutMs ?? DEFAULT_TIMEOUT)
            .then((res) => (res.ok ? res.json() : null))
            .then((value) => {
              if (value != null && ttl > 0) setCache(key, value, ttl);
            })
            .catch(() => {})
            .finally(() => _revalidating.delete(key));
        }
        return hit.value as T;
      }
    }
    const pending = _inflight.get(key);
    if (pending) {
      return pending as Promise<T>;
    }
  }

  const request = (async (): Promise<T> => {
    const res = await fetchWithTimeout(
      `${API_BASE}${path}`,
      {
        method,
        headers,
        body: opts.body && method !== "GET" && method !== "HEAD"
          ? (typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body))
          : undefined,
      },
      opts.timeoutMs ?? DEFAULT_TIMEOUT
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const detail = err?.detail ?? err?.error ?? err?.message;
      throw new Error(
        typeof detail === "string"
          ? detail
          : detail != null
            ? JSON.stringify(detail)
            : res.statusText || `HTTP ${res.status}`,
      );
    }

    const value = (await res.json()) as T;
    if (isGet && ttl > 0) {
      setCache(key, value, ttl);
    }
    return value;
  })();

  if (isGet) {
    _inflight.set(key, request);
    try {
      return await request;
    } finally {
      _inflight.delete(key);
    }
  }

  // Mutations invalidate cached reads so the next fetch is fresh.
  clearApiCache();
  return request;
}
