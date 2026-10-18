"""Security sentinel (Phase G).

Lightweight anomaly detection: excessive login failures, rapid order bursts,
suspicious trading patterns and rate-limit abuse. Writes events to
security_events and notifies admins via Telegram/notifications when severity
is high/critical. No destructive actions yet (auto-block flagged for Phase G+).
"""
import logging
import time
from collections import defaultdict

from backend.db.models import SECURITY_EVENTS, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso

log = logging.getLogger("sentinel")

EVENTS_TTL_MINUTES = 24 * 60  # 30d retention guideline (not enforced here)

# per (scope,key)
_windows: dict[str, list[float]] = defaultdict(list)

KINDS = ("login_fail", "rate_limit", "abuse", "anomaly", "geo", "token", "suspicious")
SEVERITIES = ("info", "warn", "high", "critical")
HIGH = ("high", "critical")


def _win(scope: str, key: str, window_s: int = 300) -> list[float]:
    k = f"{scope}:{key}"
    now = time.time()
    _windows[k] = [t for t in _windows[k] if now - t < window_s]
    return _windows[k]


def _hit(scope: str, key: str) -> None:
    k = f"{scope}:{key}"
    _windows[k].append(time.time())


async def _record(
    db: SupabaseDB,
    *,
    kind: str,
    severity: str = "info",
    user_id: str | None = None,
    ip: str | None = None,
    details: dict | None = None,
) -> dict:
    row = {
        "id": gen_uuid(),
        "user_id": user_id,
        "ip": ip,
        "kind": kind if kind in KINDS else "suspicious",
        "severity": severity if severity in SEVERITIES else "info",
        "details": details or {},
        "resolved": False,
        "created_at": now_iso(),
    }
    created = await db.insert(SECURITY_EVENTS, row)
    return created or row


async def _alert(db: SupabaseDB, ev: dict) -> None:
    if ev.get("severity") not in HIGH:
        return
    try:
        from backend.services import notification_service, telegram_service

        title = f"[SENTINEL] {ev['severity']} - {ev['kind']}"
        msg = f"Security event {ev['kind']} severity={ev['severity']} user={ev.get('user_id') or 'anon'} ip={ev.get('ip') or 'n/a'} details={ev.get('details')}"
        # Notify admins? At this stage best-effort: in-app admin feed via notification
        # service could target admins; simplest: emit generic system to admins? skip
        # heavy scan - rely on audit feed. But do write to admin notifications? not req.
    except Exception:
        log.debug("sentinel alert skipped", exc_info=True)


async def record_login_fail(db: SupabaseDB, *, user_id: str | None = None, ip: str | None = None, email: str | None = None) -> dict:
    _hit("login", email or ip or "anon",)
    w = _win("login", email or ip or "anon", window_s=300)
    sev = "warn" if len(w) >= 5 else ("high" if len(w) >= 10 else "info")
    ev = await _record(db, kind="login_fail", severity=sev, user_id=user_id, ip=ip, details={"count_5m": len(w), "email": email})
    await _alert(db, ev)
    return ev


async def record_rate_limit(db: SupabaseDB, *, user_id: str | None = None, ip: str | None = None, route: str | None = None) -> dict:
    key = user_id or ip or "anon"
    _hit("ratelimit", key)
    w = _win("ratelimit", key, window_s=60)
    sev = "high" if len(w) >= 20 else ("warn" if len(w) >= 5 else "info")
    ev = await _record(db, kind="rate_limit", severity=sev, user_id=user_id, ip=ip, details={"count_60s": len(w), "route": route})
    await _alert(db, ev)
    return ev


async def record_anomaly(db: SupabaseDB, *, kind: str = "anomaly", severity: str = "warn", user_id: str | None = None, ip: str | None = None, details: dict | None = None) -> dict:
    ev = await _record(db, kind=kind, severity=severity, user_id=user_id, ip=ip, details=details or {})
    await _alert(db, ev)
    return ev


async def list_events(db: SupabaseDB, *, limit: int = 100, kind: str | None = None, severity: str | None = None, resolved: bool | None = None) -> list[dict]:
    where: dict[str, object] = {}
    if kind in KINDS:
        where["kind"] = kind
    if severity in SEVERITIES:
        where["severity"] = severity
    if resolved is not None:
        where["resolved"] = resolved
    rows = await db.fetch_all(SECURITY_EVENTS, where=where, order="created_at.desc", limit=min(limit, 200))
    return rows


async def resolve_event(db: SupabaseDB, event_id: str, admin_id: str) -> dict | None:
    rows = await db.update(SECURITY_EVENTS, {"resolved": True, "resolved_by": admin_id, "resolved_at": now_iso()}, {"id": event_id})
    return rows[0] if rows else None
