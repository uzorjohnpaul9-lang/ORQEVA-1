"""Background engine scheduler: periodic autonomous market scans."""
import asyncio
import logging
import os

log = logging.getLogger("scheduler")


def _enabled() -> bool:
    return os.getenv("SCAN_ENABLED", "1").lower() not in ("0", "false", "no")


def _interval_seconds() -> int:
    minutes = float(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    return max(60, int(minutes * 60))


def _cooldown_hours() -> int:
    return max(0, int(os.getenv("SCAN_COOLDOWN_HOURS", "4")))


_last_scan: dict | None = None
_alerted_events: set[str] = set()


def get_last_scan() -> dict | None:
    """Most recent scheduler scan summary (for /api/admin/system). Single worker, in-memory."""
    return _last_scan


async def check_event_alerts(db) -> int:
    """Warn (Telegram 'risk' + in-app) once per imminent high-impact event.

    Never raises. Free tier is excluded from Telegram risk alerts by the
    existing tier gating in telegram_service.
    """
    try:
        from backend.services import calendar_service, telegram_service
        from backend.services import notification_service as notif_service
        from backend.db.models import USERS

        events = calendar_service.high_impact_soon(calendar_service.alert_window_minutes())
    except Exception:
        return 0

    sent = 0
    for ev in events:
        key = f"{ev.get('name')}|{ev.get('time_utc')}"
        if key in _alerted_events:
            continue
        _alerted_events.add(key)

        text = telegram_service.format_event_alert(ev)
        try:
            await telegram_service.broadcast(db, "risk", {"all": text})
        except Exception:
            pass

        try:
            users = await db.fetch_all(USERS, where={"is_active": True})
            mins = ev.get("minutes_away")
            when = f"in {round(float(mins))} min" if isinstance(mins, (int, float)) else "soon"
            for u in users:
                await notif_service.create(
                    db, u["id"], "event",
                    f"High-impact event {when}: {ev.get('name')}",
                    "May affect " + ", ".join(ev.get("affected_markets") or []) if ev.get("affected_markets") else "Scheduled market event ahead.",
                    respect_prefs=True,
                )
        except Exception:
            pass
        sent += 1
    return sent


async def run_scheduled_scan() -> dict:
    """One scan tick with its own SupabaseDB facade. Never raises."""
    global _last_scan
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service, outcome_service

    try:
        db = SupabaseDB(await get_service_client())
        alerts = await check_event_alerts(db)
        out = await engine_service.run_scan(db, cooldown_hours=_cooldown_hours())
        try:
            # Hard ceiling so a stalled provider can never wedge the tick loop.
            budget = int(os.getenv("OUTCOME_RESOLVE_BUDGET_SECONDS", "240"))
            resolved = await asyncio.wait_for(
                outcome_service.resolve_active_signals(db, budget_seconds=budget),
                timeout=budget + 60,
            )
        except Exception as e:  # pragma: no cover - defensive
            resolved = {"error": str(e)[:150]}
        log.info(
            "scheduled scan: %s signals (%s), errors=%s, resolved=%s",
            out["signals_generated"], out["by_market"], out["errors"], resolved,
        )
        from backend.monitoring.metrics import record_scan
        record_scan(out["signals_generated"], bool(out["errors"]))
        summary = {k: out[k] for k in ("signals_generated", "by_market", "errors")}
        summary["resolved"] = resolved
        summary["event_alerts"] = alerts
        summary["at"] = __import__("backend.db.supabase", fromlist=["now_iso"]).now_iso()
        _last_scan = summary
        return summary
    except Exception as e:
        log.exception("scheduled scan failed: %s", e)
        from backend.monitoring.metrics import record_scan
        record_scan(0, True)
        _last_scan = {"signals_generated": 0, "by_market": {}, "errors": [str(e)[:150]],
                      "at": __import__("backend.db.supabase", fromlist=["now_iso"]).now_iso()}
        return _last_scan


async def _loop():
    interval = _interval_seconds()
    startup_delay = max(0, int(os.getenv("SCAN_STARTUP_DELAY_SECONDS", "20")))
    log.info("engine scheduler started (every %ss, first scan in %ss)", interval, startup_delay)
    # One early scan so a fresh deploy resolves outcomes without waiting a full interval.
    await asyncio.sleep(startup_delay)
    await run_scheduled_scan()
    while True:
        await asyncio.sleep(interval)
        await run_scheduled_scan()


_task: asyncio.Task | None = None


def start() -> None:
    global _task
    if _enabled() and (_task is None or _task.done()):
        _task = asyncio.create_task(_loop(), name="engine-scheduler")


async def stop() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(_task), timeout=3)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass
    _task = None