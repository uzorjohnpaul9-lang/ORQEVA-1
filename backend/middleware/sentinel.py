"""Security sentinel middleware (Phase G).

Watches every request for:
  * honeypot paths (wp-admin, .env, .git, xmlrpc, ...) -> always 404 + block
  * sensitive-path probes on /api/admin and friends
  * SQLi / XSS / traversal patterns in path + query
  * 401/403/429 spikes per IP (auth failures and rate-limit abuse)
  * new-IP admin access (recorded by auth.require_admin)

Rules become rows in `security_events`; repeat offenders get an auto-block
(row in `blocked_ips` with a TTL) enforced here and expired by the scheduler.
Alerts (in-app + Telegram) fire for high/critical severity.

Everything is best-effort: any failure must never break the request.
This complements - not replaces - Cloudflare WAF and Supabase RLS.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("sentinel")

# --- tuning -----------------------------------------------------------------
WINDOW_SECONDS = 300          # 5 minute sliding window
AUTH_FAIL_LIMIT = 10          # 401/403/429 from one IP -> event
BLOCK_AFTER = 20              # ... -> auto-block
BLOCK_TTL_SECONDS = 3600      # 1 hour default TTL
HONEYPOT_TTL_SECONDS = 24 * 3600
BLOCK_REFRESH_SECONDS = 60    # reload blocklist this often
MAX_TRACKED_IPS = 5000        # cap in-memory maps (single process)

# always-404 paths; hitting one is never legitimate traffic here
HONEYPOT_PATHS = (
    "/wp-admin", "/wp-login.php", "/xmlrpc.php", "/.env", "/.git",
    "/.git/config", "/.git/HEAD", "/wp-content", "/phpmyadmin",
    "/adminer.php", "/.aws/credentials", "/vendor/phpunit",
    "/cgi-bin/", "/actuator/env", "/manager/html",
)

# paths that probing bots like to hit (record, don't auto-block alone)
SENSITIVE_PREFIXES = (
    "/api/admin", "/api/.env", "/api/../", "/api/admin/users",
)

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("sqli", re.compile(
        r"(\bunion\b.+\bselect\b|\bor\b\s+1\s*=\s*1|--\s|;--|\binformation_schema\b"
        r"|\bsleep\s*\(|\bbenchmark\s*\(|'\s*or\s*'|\"\s*or\s*\")", re.I)),
    ("xss", re.compile(r"(<script|javascript:|onerror\s*=|onload\s*=|document\.cookie)", re.I)),
    ("traversal", re.compile(r"(\.\./|\.\.%2f|%2e%2e|%252e|/etc/passwd|c:\\windows)", re.I)),
]

# per-IP auth/rate failure timestamps
_failures: dict[str, list[float]] = defaultdict(list)
# ip -> expiry (unix)
_blocked: dict[str, float] = {}
_blocklist_loaded_at = 0.0


def client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ip_blocked(ip: str) -> float:
    """Expiry timestamp if blocked, else 0.0 (expired entries self-clean)."""
    exp = _blocked.get(ip)
    if not exp:
        return 0.0
    if exp <= time.time():
        _blocked.pop(ip, None)
        return 0.0
    return exp


def block_ip(ip: str, ttl: int = BLOCK_TTL_SECONDS) -> None:
    """In-memory block (persist happens async in the same call site)."""
    if len(_blocked) > MAX_TRACKED_IPS:
        _blocked.clear()
    _blocked[ip] = time.time() + ttl


def unblock_ip(ip: str) -> None:
    _blocked.pop(ip, None)


def is_blocked(ip: str) -> bool:
    return _ip_blocked(ip) > 0.0


def _scan(path: str, query: str) -> str | None:
    """Return the offending pattern name, or None when clean.

    Path and query are URL-decoded first: attackers percent-encode probes
    (`%27%20OR%20`) and a raw match would miss them.
    """
    from urllib.parse import unquote_plus

    hay = unquote_plus(f"{path}?{query}")
    for name, pat in _PATTERNS:
        if pat.search(hay):
            return name
    return None


def _honeypot(path: str) -> bool:
    p = path.lower()
    return any(p.startswith(h) or h in p for h in HONEYPOT_PATHS)


def _note_failure(ip: str) -> int:
    now = time.time()
    if len(_failures) > MAX_TRACKED_IPS:
        _failures.clear()
    bucket = _failures[ip]
    bucket.append(now)
    cutoff = now - WINDOW_SECONDS
    bucket[:] = [t for t in bucket if t >= cutoff]
    return len(bucket)


def _clear_failures(ip: str) -> None:
    _failures.pop(ip, None)


# --- persistence (never raises) --------------------------------------------
async def _persist_event(ip: str, kind: str, severity: str, details: dict) -> None:
    """Record a security event; sentinel_service.alerts admins on high/critical."""
    try:
        from backend.db.supabase import get_service_client, SupabaseDB
        from backend.services import sentinel_service

        client = await get_service_client()
        await sentinel_service.record_anomaly(
            SupabaseDB(client), kind=kind, severity=severity, ip=ip, details=details
        )
    except Exception:
        logger.debug("sentinel persist failed", exc_info=True)


async def _persist_block(ip: str, reason: str, ttl: int) -> None:
    try:
        from datetime import datetime, timedelta, timezone

        from backend.db.models import BLOCKED_IPS
        from backend.db.supabase import SupabaseDB, get_service_client, now_iso

        client = await get_service_client()
        db = SupabaseDB(client)
        exp = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat().replace("+00:00", "Z")
        existing = await db.fetch_one(BLOCKED_IPS, {"ip": ip})
        if existing:
            await db.update(
                BLOCKED_IPS,
                {"reason": reason[:200], "blocked_until": exp,
                 "hits": int(existing.get("hits") or 0) + 1, "cleared_at": None},
                {"ip": ip},
            )
        else:
            await db.insert(BLOCKED_IPS, {
                "ip": ip, "reason": reason[:200], "hits": 1,
                "blocked_until": exp, "created_at": now_iso(),
                "created_by": "sentinel", "cleared_at": None,
            })
    except Exception:
        logger.debug("sentinel block persist failed", exc_info=True)


async def _load_blocks(force: bool = False) -> None:
    global _blocklist_loaded_at
    now = time.time()
    if not force and now - _blocklist_loaded_at < BLOCK_REFRESH_SECONDS:
        return
    _blocklist_loaded_at = now
    try:
        from backend.db.supabase import get_service_client, SupabaseDB, now_iso
        from backend.db.models import BLOCKED_IPS

        client = await get_service_client()
        db = SupabaseDB(client)
        rows = await db.fetch_all(
            BLOCKED_IPS,
            where={"blocked_until": {"op": "gt", "value": now_iso()},
                   "cleared_at": {"op": "is", "value": None}},
            limit=2000,
        )
        for r in rows:
            if r.get("ip"):
                _blocked[r["ip"]] = _ts(r.get("blocked_until")) or (now + BLOCK_TTL_SECONDS)
    except Exception:
        logger.debug("sentinel blocklist load failed", exc_info=True)


def _ts(value) -> float | None:
    from backend.db.supabase import parse_dt
    dt = parse_dt(value)
    return dt.timestamp() if dt else None


def _spawn(coro) -> None:
    """Fire-and-forget a coroutine without ever failing the request."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_wrap(coro))


async def _wrap(coro) -> None:
    try:
        await coro
    except Exception:
        logger.debug("sentinel task failed", exc_info=True)


class SentinelMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            # admin/deploy tooling bypasses nothing; only skip static assets
            if request.method == "OPTIONS":
                return await call_next(request)

            ip = client_ip(request)
            path = request.url.path
            query = request.url.query or ""

            if is_blocked(ip):
                return Response(
                    content='{"detail":"Forbidden"}',
                    status_code=403,
                    media_type="application/json",
                    headers={"X-Sentinel": "blocked"},
                )

            await _load_blocks()  # throttled by BLOCK_REFRESH_SECONDS

            if _honeypot(path):
                _spawn(_persist_event(ip, "abuse", "high",
                                      {"path": path, "rule": "honeypot"}))
                _spawn(_persist_block(ip, f"honeypot:{path}", HONEYPOT_TTL_SECONDS))
                block_ip(ip, HONEYPOT_TTL_SECONDS)
                return Response(content='{"detail":"Not Found"}', status_code=404,
                                media_type="application/json")

            hit = _scan(path, query)
            if hit:
                _spawn(_persist_event(ip, "suspicious", "high",
                                      {"path": path, "query": query[:500], "rule": hit}))
                _spawn(_persist_block(ip, f"{hit}:{path}", BLOCK_TTL_SECONDS))
                block_ip(ip, BLOCK_TTL_SECONDS)
                return Response(content='{"detail":"Forbidden"}', status_code=403,
                                media_type="application/json")

            if any(path.startswith(p) for p in SENSITIVE_PREFIXES):
                _spawn(_persist_event(ip, "geo", "info", {"path": path, "rule": "sensitive_path"}))

            response = await call_next(request)

            if response.status_code in (401, 403, 429):
                n = _note_failure(ip)
                if n >= AUTH_FAIL_LIMIT:
                    sev = "high" if n >= BLOCK_AFTER else "warn"
                    _spawn(_persist_event(ip, "rate_limit", sev,
                                          {"path": path, "count": n,
                                           "status": response.status_code}))
                    if n >= BLOCK_AFTER:
                        _spawn(_persist_block(ip, f"auth_spike:{n}", BLOCK_TTL_SECONDS))
                        block_ip(ip, BLOCK_TTL_SECONDS)
                        _clear_failures(ip)
            elif response.status_code < 400:
                # a success resets the failure streak (avoid punishing shared NATs)
                if _failures.get(ip):
                    _clear_failures(ip)

            return response
        except Exception:
            # sentinel must never take the API down
            logger.debug("sentinel dispatch error", exc_info=True)
            try:
                return await call_next(request)
            except Exception:
                return Response(content='{"detail":"Internal Server Error"}',
                                status_code=500, media_type="application/json")
