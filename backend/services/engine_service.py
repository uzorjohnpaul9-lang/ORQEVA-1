"""Engine scan orchestration shared by the admin endpoint and the background scheduler."""
import asyncio
import os
from typing import Any

from backend.db.models import SIGNALS, USERS
from backend.db.supabase import SupabaseDB, now_iso
from backend.services import signal_service

# (bucket, module, class, strategy, tier, db_market)
# bucket = result grouping; db_market = value stored in signals.market
_ENGINE_SPECS = [
    ("stock", "engines.stock_engine", "StockEngine", "Alpaca Breakout", "premium", "stock"),
    ("forex", "engines.forex_engine", "ForexEngine", "Twelve Data Trend", "free", "forex"),
    ("crypto", "engines.crypto_engine", "CryptoEngine", "Crypto Momentum", "vip", "crypto"),
    ("crypto_alt", "engines.crypto_alt_engine", "CryptoAltEngine", "Meme Momentum", "vip", "crypto"),
    ("commodity", "engines.commodity_engine", "CommodityEngine", "Commodity Trend", "premium", "commodity"),
]


def _empty_results() -> dict[str, list]:
    return {"stock": [], "forex": [], "crypto": [], "crypto_alt": [], "commodity": []}


def _engine_signal_to_db(signal, market: str, strategy: str, tier: str = "free",
                         event_context: dict | None = None) -> dict:
    indicators = dict(signal.metadata or {})
    data_source = indicators.pop("data_source", None) or "live"
    if event_context:
        indicators["event_context"] = event_context
    return {
        "symbol": signal.symbol,
        "market": market,
        # Engines emit "BUY"/"SELL"; rows are stored lowercased, so normalise
        # here too - otherwise the cooldown lookup never matches the stored
        # signal and the same call gets published over and over.
        "direction": str(signal.direction or "").lower(),
        "confidence": round(signal.confidence, 4),
        "entry_price": round(signal.price, 4),
        "stop_loss": round(signal.stop_loss, 4),
        "take_profit": round(signal.target_price, 4),
        "strategy": (signal.metadata or {}).get("strategy") or strategy,
        "tier": tier,
        "indicators": indicators,
        "data_source": data_source,
    }


async def recent_signal_keys(
    db: SupabaseDB, hours: int, symbols: list[str] | None = None
) -> set[tuple[str, str, str]]:
    """(symbol, market, direction) tuples emitted within the cooldown window.

    ``symbols`` narrows the query server-side. Without it PostgREST's
    1000-row cap silently truncates the window - a busy table has thousands of
    rows in 24h - so the cooldown misses signals and duplicates get published.
    The rows are paged through for the same reason.
    """
    from datetime import datetime, timedelta, timezone

    if symbols is not None and not symbols:
        return set()

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    where: dict[str, Any] = {"created_at": {"op": "gte", "value": cutoff}}
    if symbols is not None:
        where["symbol"] = sorted(set(symbols))

    rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        chunk = await db.fetch_all(
            SIGNALS,
            where=where,
            columns="symbol,market,direction",
            limit=page_size,
            offset=offset,
        )
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size
    return {(r.get("symbol"), r.get("market"), r.get("direction")) for r in rows}


async def run_scan(db: SupabaseDB, *, cooldown_hours: int = 0) -> dict:
    """Run all engines once, save new signals, fan out notifications.

    Returns {"signals_generated", "by_market", "errors", "saved"}.
    """
    results: dict[str, list] = _empty_results()
    errors: list[str] = []

    try:
        from backend.services import calendar_service
        event_context = calendar_service.event_context()
    except Exception:
        event_context = None

    for bucket, mod_name, cls_name, strategy, tier, db_market in _ENGINE_SPECS:
        try:
            module = __import__(mod_name, fromlist=[cls_name])
            engine = getattr(module, cls_name)()
            if await asyncio.to_thread(engine.is_market_hours):
                raw = await asyncio.to_thread(engine.run_cycle)
                results[bucket].extend(
                    _engine_signal_to_db(s, db_market, strategy, tier, event_context) for s in raw
                )
        except Exception as e:
            errors.append(f"{bucket} engine: {str(e)[:150]}")

    if cooldown_hours > 0:
        candidate_symbols = {s["symbol"] for sigs in results.values() for s in sigs}
        seen = await recent_signal_keys(db, cooldown_hours, symbols=sorted(candidate_symbols))
        for bucket, sigs in results.items():
            results[bucket] = [
                s for s in sigs if (s["symbol"], s["market"], s["direction"]) not in seen
            ]

    # Confidence split: strong free-tier calls become premium so the free plan
    # keeps the everyday subset and the best calls sit behind an upgrade.
    promoted = 0
    for sigs in results.values():
        promoted += signal_service.split_free_signals(sigs)

    # Only live-data signals are published. Engines fall back to simulated
    # prices when no real source is reachable; those are dropped here so users
    # never see a signal that wasn't derived from real market data.
    all_signals = [s for sigs in results.values() for s in sigs]
    dropped_simulated = sum(1 for s in all_signals if s.get("data_source") != "live")
    all_signals = [s for s in all_signals if s.get("data_source") == "live"]
    for bucket, sigs in results.items():
        results[bucket] = [s for s in sigs if s.get("data_source") == "live"]
    saved: list[dict] = []
    if all_signals:
        saved = await signal_service.save_signals_batch(db, all_signals)
        await _auto_trade(db, saved, errors)
        await _fan_out(db, results, saved, errors)

    from backend.middleware.cache import cache
    cache.clear()

    return {
        "signals_generated": len(saved),
        "by_market": {k: len(v) for k, v in results.items()},
        "promoted_to_premium": promoted,
        "dropped_simulated": dropped_simulated,
        "errors": errors,
        "saved": saved,
    }


async def _auto_trade(db: SupabaseDB, saved: list[dict], errors: list[str]) -> None:
    """Let Auto-Trade place orders for opted-in users. Failures never break the scan."""
    try:
        from backend.services import auto_trade_service
        await auto_trade_service.run_for_scan(db, saved)
    except Exception as e:
        errors.append(f"auto-trade: {str(e)[:150]}")


async def _fan_out(db: SupabaseDB, results: dict, saved: list[dict], errors: list) -> None:
    """Telegram broadcast + in-app notifications for fresh signals."""
    from backend.services import telegram_service
    from backend.services import notification_service as notif_service

    try:
        by_tier: dict[str, list[dict]] = {}
        for s in saved:
            by_tier.setdefault(s.get("tier_required") or "free", []).append(s)
        if by_tier:
            await telegram_service.queue_channel_signals(by_tier)
            # Channel fan-out is latency-aware: each channel releases a signal
            # once it has aged past that channel tier's own delay.
            await telegram_service.flush_channel_signals()
        if saved:
            await telegram_service.broadcast_signals(db, saved)
    except Exception as e:
        errors.append(f"Telegram broadcast: {str(e)[:150]}")

    try:
        users = await db.fetch_all(USERS, where={"is_active": True})
        top = [s for s in saved if s.get("confidence") and float(s["confidence"]) >= 0.6][:5]
        if not top or not users:
            return
        # Fan-out is I/O bound (2 HTTP calls per notification), so run it with a
        # bounded worker pool instead of serially: one sequential pass per user,
        # users processed concurrently. Keeps a large user base from wedging the
        # scan tick.
        concurrency = max(1, int(os.getenv("NOTIFY_FANOUT_CONCURRENCY", "20")))

        async def _notify_user(u: dict) -> None:
            for s in top:
                await notif_service.create(
                    db, u["id"], "signal",
                    f"{s.get('direction')} signal: {s.get('symbol')}",
                    f"{s.get('market', '').title()} · confidence {float(s.get('confidence', 0)) * 100:.0f}% · {s.get('strategy')}",
                    respect_prefs=True,
                )

        sem = asyncio.Semaphore(concurrency)

        async def _guarded(u: dict) -> None:
            async with sem:
                await _notify_user(u)

        await asyncio.gather(*(_guarded(u) for u in users))
    except Exception:
        pass