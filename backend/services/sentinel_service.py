"""Security sentinel (Phase G).

Lightweight anomaly detection: excessive login failures, rate-limit abuse,
honeypot hits, injection/traversal probes and unusual admin access. Writes
events to `security_events` (admin Security tab), auto-blocks repeat
offenders in `blocked_ips` (enforced by backend.middleware.sentinel) and
alerts admins (in-app + Telegram) when severity is high/critical.

Every public recorder is failure-tolerant: a database hiccup must never
turn a login 401 into a 500.
"""
import logging
import time
from collections import defaultdict

from backend.db.models import BLOCKED_IPS, SECURITY_EVENTS, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso, parse_dt

log = logging.getLogger("sentinel")

# per (scope,key) sliding windows
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
    _windows[f"{scope}:{key}"].append(time.time())


async def _alert(db: SupabaseDB, ev: dict) -> None:
    """Ping active admins (in-app always, Telegram when chat id present)."""
    if ev.get("severity") not in HIGH:
        return
    try:
        from backend.db.models import USERS
        from backend.services import notification_service, telegram_service

        title = f"[Sentinel] {ev['severity'].upper()} - {ev['kind']}"
        msg = (
            f"IP {ev.get('ip') or 'n/a'} · user {ev.get('user_id') or 'anon'} · "
            f"{ev.get('details') or {}}"
        )
        admins = await db.fetch_all(USERS, where={"is_admin": True, "is_active": True}, limit=20)
        for a in admins:
            await notification_service.create(db, a["id"], "security", title, msg,
                                              respect_prefs=False)
        chat = admins[0].get("telegram_chat_id") if admins else None
        if chat:
            try:
                await telegram_service.send_message(chat, f"{title}\n{msg}")
            except Exception:
                pass
    except Exception:
        log.debug("sentinel alert skipped", exc_info=True)


async def _record(
    db: SupabaseDB,
    *,
    kind: str,
    severity: str = "info",
    user_id: str | None = None,
    ip: str | None = None,
    details: dict | None = None,
) -> dict | None:
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
    try:
        created = await db.insert(SECURITY_EVENTS, row)
        return created or row
    except Exception:
        log.debug("security event persist failed", exc_info=True)
        return None


async def record_login_fail(db: SupabaseDB, *, user_id: str | None = None,
                            ip: str | None = None, email: str | None = None) -> dict | None:
    _hit("login", email or ip or "anon")
    w = _win("login", email or ip or "anon", window_s=300)
    sev = "info" if len(w) < 5 else ("warn" if len(w) < 10 else "high")
    ev = await _record(db, kind="login_fail", severity=sev, user_id=user_id, ip=ip,
                       details={"count_5m": len(w), "email": email})
    if ev:
        await _alert(db, ev)
    return ev


async def record_rate_limit(db: SupabaseDB, *, user_id: str | None = None,
                            ip: str | None = None, route: str | None = None) -> dict | None:
    key = user_id or ip or "anon"
    _hit("ratelimit", key)
    w = _win("ratelimit", key, window_s=60)
    sev = "info" if len(w) < 5 else ("warn" if len(w) < 20 else "high")
    ev = await _record(db, kind="rate_limit", severity=sev, user_id=user_id, ip=ip,
                       details={"count_60s": len(w), "route": route})
    if ev:
        await _alert(db, ev)
    return ev


async def record_anomaly(db: SupabaseDB, *, kind: str = "anomaly", severity: str = "warn",
                         user_id: str | None = None, ip: str | None = None,
                         details: dict | None = None) -> dict | None:
    ev = await _record(db, kind=kind, severity=severity, user_id=user_id, ip=ip,
                       details=details or {})
    if ev:
        await _alert(db, ev)
    return ev


async def list_events(db: SupabaseDB, *, limit: int = 100, kind: str | None = None,
                      severity: str | None = None, resolved: bool | None = None) -> list[dict]:
    where: dict[str, object] = {}
    if kind in KINDS:
        where["kind"] = kind
    if severity in SEVERITIES:
        where["severity"] = severity
    if resolved is not None:
        where["resolved"] = resolved
    rows = await db.fetch_all(SECURITY_EVENTS, where=where, order="created_at.desc",
                              limit=min(limit, 200))
    return rows


async def resolve_event(db: SupabaseDB, event_id: str, admin_id: str) -> dict | None:
    rows = await db.update(
        SECURITY_EVENTS,
        {"resolved": True, "resolved_by": admin_id, "resolved_at": now_iso()},
        {"id": event_id},
    )
    return rows[0] if rows else None


# --- blocklist (admin view / manual controls; enforcement lives in middleware) ---
async def list_blocks(db: SupabaseDB, *, active_only: bool = True, limit: int = 200) -> list[dict]:
    where: dict[str, object] = {}
    if active_only:
        where["blocked_until"] = {"op": "gt", "value": now_iso()}
        where["cleared_at"] = None
    try:
        return await db.fetch_all(BLOCKED_IPS, where=where, order="created_at.desc",
                                  limit=min(limit, 500))
    except Exception:
        log.debug("blocklist read failed", exc_info=True)
        return []


async def unblock(db: SupabaseDB, ip: str, admin: dict) -> dict | None:
    try:
        rows = await db.update(BLOCKED_IPS, {"cleared_at": now_iso()}, {"ip": ip})
    except Exception:
        log.debug("unblock persist failed", exc_info=True)
        rows = []
    try:
        from backend.middleware import sentinel

        sentinel.unblock_ip(ip)
    except Exception:
        pass
    if rows:
        from backend.services import admin_service
        try:
            await admin_service.log_action(db, admin, "sentinel.unblock", "blocked_ip", ip, {})
        except Exception:
            pass
    return rows[0] if rows else None


async def expire_stale_blocks(db: SupabaseDB) -> int:
    """Called by the scheduler: clear rows whose TTL passed + drop memory."""
    now = now_iso()
    try:
        rows = await db.fetch_all(
            BLOCKED_IPS,
            where={"blocked_until": {"op": "lt", "value": now}, "cleared_at": None},
            limit=500,
        )
        for r in rows:
            await db.update(BLOCKED_IPS, {"cleared_at": now}, {"id": r["id"]})
            try:
                from backend.middleware import sentinel
                sentinel.unblock_ip(r.get("ip") or "")
            except Exception:
                pass
        return len(rows)
    except Exception:
        log.debug("block expiry failed", exc_info=True)
        return 0
