"""Live broker bridge health monitor.

A dead MT5 bridge is operationally different from one bad signal: every live
order for every user is paused until the tunnel comes back. This service probes
the configured venue once per scheduler tick, keeps the last result in memory
for the health endpoint, and alerts the connection owner on state changes
(down / recovered) instead of waiting for an auto-trade skip.
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import time

from backend.db.models import EXCHANGE_CONNECTIONS, USERS
from backend.db.supabase import SupabaseDB, now_iso
from backend.exchanges import get_adapter
from backend.services import notification_service, telegram_service

log = logging.getLogger("broker_health")

_DEFAULT_INTERVAL = 3600.0
_state: dict[str, dict] = {}


def _alert_interval() -> float:
    try:
        return max(60.0, float(os.getenv("BROKER_HEALTH_ALERT_INTERVAL_SECONDS", "3600")))
    except ValueError:
        return _DEFAULT_INTERVAL


def _key(conn: dict) -> str:
    return f"{conn.get('exchange') or ''}:{conn.get('id') or ''}"


def _next_action(previous: dict | None, ok: bool, now: float,
                 interval: float) -> str | None:
    """'down' / 'recovered' / None for a health transition.

    Alerts fire on every state change and, while still down, at most once per
    interval so a long outage does not spam the user every scan.
    """
    if previous is None:
        return None if ok else "down"
    was_ok = bool(previous.get("ok"))
    if was_ok and not ok:
        return "down"
    if not was_ok and ok:
        return "recovered"
    if not ok:
        alerted_at = float(previous.get("alerted_at") or 0)
        if now - alerted_at >= interval:
            return "down"
    return None


def status() -> dict:
    """Aggregate cached bridge status for /api/health (no network calls)."""
    entries = [s for s in _state.values() if s.get("reachable") is not None]
    if not entries:
        return {"checked": False}
    latest = max(entries, key=lambda s: s.get("checked_ts") or 0)
    return {
        "checked": True,
        "reachable": all(bool(s.get("reachable")) for s in entries),
        "mt5_available": all(bool(s.get("mt5_available")) for s in entries),
        "last_checked": latest.get("checked_at"),
        "last_error": latest.get("detail") if not latest.get("ok") else None,
        "checked_connections": len(entries),
        "down_connections": sum(1 for s in entries if not s.get("ok")),
    }


def reset() -> None:
    _state.clear()


async def _send_alert(db: SupabaseDB, conn: dict, ok: bool, detail: str | None) -> bool:
    user = await db.fetch_one(USERS, {"id": conn.get("user_id")},
                              columns="id,tier,telegram_chat_id")
    if not user:
        return False
    venue = (conn.get("exchange") or "broker").title()
    if ok:
        title = f"{venue} bridge back online"
        message = ("Live order routing and account reads are working again. "
                   "Live auto-trade has resumed.")
        ntype = "system"
    else:
        title = f"{venue} bridge unreachable - live trading paused"
        reason = html.escape(str(detail or "bridge unreachable"))[:300]
        message = (f"Live auto-trade is paused and live orders are being skipped. "
                   f"Reason: {reason}. Check the MT5 bridge and tunnel on the VPS.")
        ntype = "trade_warning"
    try:
        await notification_service.create(db, user["id"], ntype, title, message)
    except Exception:
        pass
    try:
        await telegram_service.notify_user(
            db, user, "system", f"<b>{html.escape(title)}</b>\n{message}"
        )
    except Exception:
        pass
    return True


async def check_and_alert(db: SupabaseDB) -> dict:
    """Probe every active live venue and alert on transition. Never raises."""
    checked = down = alerts = 0
    try:
        conns = await db.fetch_all(
            EXCHANGE_CONNECTIONS, where={"is_active": True}, order="connected_at.desc"
        )
    except Exception as e:
        log.debug("broker health: could not load connections", exc_info=True)
        return {"checked": 0, "down": 0, "alerts": 0, "error": str(e)[:120]}

    interval = _alert_interval()
    for conn in conns:
        if conn.get("is_paper"):
            continue
        adapter = get_adapter(conn.get("exchange"))
        if adapter is None:
            continue
        try:
            result = await asyncio.to_thread(adapter.health)
        except Exception as e:  # pragma: no cover - adapter should catch
            result = {"ok": False, "reachable": False, "mt5_available": None,
                      "detail": str(e)[:200]}
        if result.get("reachable") is None:
            continue

        key = _key(conn)
        prev = _state.get(key)
        now = time.time()
        ok = bool(result.get("ok"))
        action = _next_action(prev, ok, now, interval)
        state = {
            "ok": ok,
            "reachable": result.get("reachable"),
            "mt5_available": result.get("mt5_available"),
            "detail": result.get("detail"),
            "checked_at": now_iso(),
            "checked_ts": now,
            "alerted_at": (prev or {}).get("alerted_at"),
            "last_ok_at": (prev or {}).get("last_ok_at"),
        }
        if ok:
            state["last_ok_at"] = now_iso()
        if action:
            state["alerted_at"] = now
            try:
                await _send_alert(db, conn, ok, result.get("detail"))
                alerts += 1
            except Exception:
                log.debug("broker health alert failed", exc_info=True)
        _state[key] = state
        checked += 1
        if not ok:
            down += 1

    return {"checked": checked, "down": down, "alerts": alerts}
