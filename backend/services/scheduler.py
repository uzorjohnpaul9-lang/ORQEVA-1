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


def _fast_enabled() -> bool:
    # Opt-in until the term migration is applied and the lane is smoke-tested.
    return os.getenv("FAST_SCAN_ENABLED", "0").lower() not in ("0", "false", "no")


def _fast_interval_seconds() -> int:
    return max(30, int(os.getenv("FAST_SCAN_INTERVAL_SECONDS", "120")))


def _fast_resolve_interval_seconds() -> int:
    return max(30, int(os.getenv("FAST_RESOLVE_INTERVAL_SECONDS", "60")))


_last_scan: dict | None = None
_last_fast_scan: dict | None = None
_alerted_events: set[str] = set()
_last_digest_date: str | None = None


def get_last_scan() -> dict | None:
    """Most recent scheduler scan summary (for /api/admin/system). Single worker, in-memory."""
    return _last_scan


def get_last_fast_scan() -> dict | None:
    """Most recent fast-lane summary (for /api/admin/system)."""
    return _last_fast_scan


async def run_fast_tick(resolve_only: bool = False) -> dict:
    """One fast-lane tick. Never raises."""
    global _last_fast_scan
    from backend.db.supabase import SupabaseDB, get_service_client, now_iso
    from backend.services import engine_service, outcome_service, signal_terms

    try:
        db = SupabaseDB(await get_service_client())
        out: dict = {"signals_generated": 0, "errors": [], "by_market": {}}
        if not resolve_only:
            out = await engine_service.run_fast_scan(db)
        try:
            budget = int(os.getenv("FAST_OUTCOME_RESOLVE_BUDGET_SECONDS", "45"))
            resolved = await asyncio.wait_for(
                outcome_service.resolve_active_signals(
                    db, budget_seconds=budget, notify_expired=True,
                    terms=signal_terms.FAST_TERMS,
                ),
                timeout=budget + 20,
            )
        except Exception as e:  # pragma: no cover - defensive
            resolved = {"error": str(e)[:150]}
        summary = {
            "signals_generated": out.get("signals_generated", 0),
            "terms": out.get("terms", []),
            "by_market": out.get("by_market", {}),
            "errors": out.get("errors", []),
            "dropped_simulated": out.get("dropped_simulated", 0),
            "dropped_invalid": out.get("dropped_invalid", 0),
            "dropped_capped": out.get("dropped_capped", 0),
            "resolved": resolved,
            "at": now_iso(),
        }
        _last_fast_scan = summary
        log.info(
            "fast scan: %s signals %s, errors=%s, resolved=%s",
            summary["signals_generated"], summary["by_market"],
            summary["errors"], resolved,
        )
        return summary
    except Exception as e:
        log.exception("fast scan failed: %s", e)
        _last_fast_scan = {
            "signals_generated": 0, "by_market": {}, "errors": [str(e)[:150]],
            "at": __import__("backend.db.supabase", fromlist=["now_iso"]).now_iso(),
        }
        return _last_fast_scan


def should_send_digest(now, last_date: str | None, hour: int = 18) -> bool:
    """True when it's the weekly digest window (Sunday >= hour UTC) and the
    digest has not already been sent today."""
    if now.weekday() != 6:  # 6 == Sunday
        return False
    if now.hour < hour:
        return False
    return last_date != now.strftime("%Y-%m-%d")


async def maybe_send_weekly_digests(db) -> int:
    """Send the weekly digest once per Sunday to opted-in users. Never raises."""
    global _last_digest_date
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    try:
        hour = int(os.getenv("WEEKLY_DIGEST_HOUR_UTC", "18"))
    except ValueError:
        hour = 18
    if not should_send_digest(now, _last_digest_date, max(0, min(23, hour))):
        return 0
    # Mark first so a crash mid-send doesn't cause a second blast this tick.
    _last_digest_date = now.strftime("%Y-%m-%d")
    try:
        from backend.services import telegram_service

        sent = await telegram_service.send_weekly_digests(db)
        log.info("weekly digest sent to %s users", sent)
        return sent
    except Exception as e:  # pragma: no cover - defensive
        log.warning("weekly digest failed: %s", str(e)[:150])
        return 0


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
        try:
            # A dead bridge pauses every live order; alert on the transition
            # instead of waiting for the next auto-trade skip.
            from backend.services import broker_health_service
            broker_health = await broker_health_service.check_and_alert(db)
        except Exception:  # pragma: no cover - defensive
            broker_health = {}
        alerts = await check_event_alerts(db)
        out = await engine_service.run_scan(db, cooldown_hours=_cooldown_hours())
        try:
            # Phase J: release latency-deferred channel posts / per-user alerts.
            from backend.services import telegram_service
            deferred = await telegram_service.flush_deferred(db)
        except Exception:  # pragma: no cover - defensive
            deferred = 0
        try:
            # Hard ceiling so a stalled provider can never wedge the tick loop.
            budget = int(os.getenv("OUTCOME_RESOLVE_BUDGET_SECONDS", "240"))
            resolved = await asyncio.wait_for(
                outcome_service.resolve_active_signals(
                    db, budget_seconds=budget, notify_expired=True,
                    skip_fast=True,
                ),
                timeout=budget + 60,
            )
        except Exception as e:  # pragma: no cover - defensive
            resolved = {"error": str(e)[:150]}
        try:
            # Retry any signal-linked position that could not be closed at
            # resolution time (e.g. the broker was unreachable).
            from backend.services import order_executor
            reconciled = await order_executor.reconcile_resolved_trades(db)
        except Exception:  # pragma: no cover - defensive
            reconciled = {}
        try:
            digest = await maybe_send_weekly_digests(db)
        except Exception:  # pragma: no cover - defensive
            digest = 0
        try:
            # Phase G: expire sentinel auto-blocks whose TTL has passed.
            from backend.services import sentinel_service
            expired_blocks = await sentinel_service.expire_stale_blocks(db)
        except Exception:  # pragma: no cover - defensive
            expired_blocks = 0
        try:
            # Phase J: release latency-deferred Telegram deliveries (free 5m /
            # premium 1m) even when this tick produced no new signals.
            from backend.services import telegram_service
            deferred = await telegram_service.flush_deferred(db)
        except Exception:  # pragma: no cover - defensive
            deferred = 0
        try:
            # Phase I: billing reminders, renewal invoices, grace expiry sweep.
            from backend.services import billing_service
            billing = await billing_service.billing_jobs(db)
        except Exception:  # pragma: no cover - defensive
            billing = {}
        log.info(
            "scheduled scan: %s signals (%s), errors=%s, resolved=%s, "
            "dropped_sim=%s, dropped_invalid=%s",
            out["signals_generated"], out["by_market"], out["errors"], resolved,
            out.get("dropped_simulated", 0), out.get("dropped_invalid", 0),
        )
        from backend.monitoring.metrics import record_scan
        record_scan(out["signals_generated"], bool(out["errors"]))
        summary = {k: out[k] for k in ("signals_generated", "by_market", "errors")}
        summary["promoted_to_premium"] = out.get("promoted_to_premium", 0)
        summary["dropped_simulated"] = out.get("dropped_simulated", 0)
        summary["dropped_invalid"] = out.get("dropped_invalid", 0)
        summary["resolved"] = resolved
        summary["trades_reconciled"] = reconciled
        summary["broker_health"] = broker_health
        summary["event_alerts"] = alerts
        summary["deferred_alerts"] = deferred
        summary["weekly_digest"] = digest
        summary["blocks_expired"] = expired_blocks
        summary["deferred_alerts"] = deferred
        summary["billing"] = billing
        summary["at"] = __import__("backend.db.supabase", fromlist=["now_iso"]).now_iso()
        _last_scan = summary
        return summary
    except Exception as e:
        log.exception("scheduled scan failed: %s", e)
        from backend.monitoring.metrics import record_scan
        record_scan(0, True)
        _last_scan = {"signals_generated": 0, "by_market": {}, "errors": [str(e)[:150]],
                      "dropped_simulated": 0, "dropped_invalid": 0,
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


async def _fast_loop():
    scan_interval = _fast_interval_seconds()
    resolve_interval = _fast_resolve_interval_seconds()
    startup_delay = max(0, int(os.getenv("FAST_STARTUP_DELAY_SECONDS", "45")))
    log.info(
        "fast signal scheduler started (scan %ss, resolve %ss, first in %ss)",
        scan_interval, resolve_interval, startup_delay,
    )
    await asyncio.sleep(startup_delay)
    loop = asyncio.get_running_loop()
    next_scan = loop.time()
    next_resolve = loop.time()
    while True:
        now = loop.time()
        if now >= next_scan:
            next_scan = now + scan_interval
            await run_fast_tick()
        elif now >= next_resolve:
            await run_fast_tick(resolve_only=True)
        if now >= next_resolve:
            next_resolve = now + resolve_interval
        await asyncio.sleep(max(5, min(30, next_scan - loop.time(), next_resolve - loop.time())))


_task: asyncio.Task | None = None
_fast_task: asyncio.Task | None = None


def start() -> None:
    global _task, _fast_task
    if _enabled() and (_task is None or _task.done()):
        _task = asyncio.create_task(_loop(), name="engine-scheduler")
    if _enabled() and _fast_enabled() and (_fast_task is None or _fast_task.done()):
        _fast_task = asyncio.create_task(_fast_loop(), name="fast-signal-scheduler")


async def stop() -> None:
    global _task, _fast_task
    for task in (_task, _fast_task):
        if task is not None and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=3)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
    _task = None
    _fast_task = None
