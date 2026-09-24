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


def get_last_scan() -> dict | None:
    """Most recent scheduler scan summary (for /api/admin/system). Single worker, in-memory."""
    return _last_scan


async def run_scheduled_scan() -> dict:
    """One scan tick with its own SupabaseDB facade. Never raises."""
    global _last_scan
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    try:
        db = SupabaseDB(await get_service_client())
        out = await engine_service.run_scan(db, cooldown_hours=_cooldown_hours())
        log.info(
            "scheduled scan: %s signals (%s), errors=%s",
            out["signals_generated"], out["by_market"], out["errors"],
        )
        from backend.monitoring.metrics import record_scan
        record_scan(out["signals_generated"], bool(out["errors"]))
        summary = {k: out[k] for k in ("signals_generated", "by_market", "errors")}
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
    log.info("engine scheduler started (every %ss)", interval)
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