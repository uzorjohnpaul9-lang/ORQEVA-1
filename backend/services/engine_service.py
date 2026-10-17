"""Engine scan orchestration shared by the admin endpoint and the background scheduler."""
import asyncio

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
        "direction": signal.direction,
        "confidence": round(signal.confidence, 4),
        "entry_price": round(signal.price, 4),
        "stop_loss": round(signal.stop_loss, 4),
        "take_profit": round(signal.target_price, 4),
        "strategy": (signal.metadata or {}).get("strategy") or strategy,
        "tier": tier,
        "indicators": indicators,
        "data_source": data_source,
    }


async def recent_signal_keys(db: SupabaseDB, hours: int) -> set[tuple[str, str, str]]:
    """(symbol, market, direction) tuples emitted within the cooldown window."""
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
    rows = await db.fetch_all(
        SIGNALS,
        where={"created_at": {"op": "gte", "value": cutoff}},
        columns="symbol,market,direction",
    )
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
        seen = await recent_signal_keys(db, cooldown_hours)
        for bucket, sigs in results.items():
            results[bucket] = [
                s for s in sigs if (s["symbol"], s["market"], s["direction"]) not in seen
            ]

    all_signals = [s for sigs in results.values() for s in sigs]
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
        channel_texts: dict[str, str] = {}
        for mkt, sigs in results.items():
            if not sigs:
                continue
            lines = [telegram_service.format_signal_alert(s) for s in saved if s.get("market") == mkt]
            if not lines:
                continue
            block = "<b>Engine scan - " + mkt.replace("_", " ").title() + "</b>\n" + "\n".join(lines)
            tier = sigs[0].get("tier", "free")
            channel_texts[tier] = (channel_texts[tier] + "\n\n" + block) if channel_texts.get(tier) else block
        if saved:
            await telegram_service.broadcast_signals(db, saved)
        if any(channel_texts.values()):
            await telegram_service.broadcast_channels(channel_texts)
    except Exception as e:
        errors.append(f"Telegram broadcast: {str(e)[:150]}")

    try:
        users = await db.fetch_all(USERS, where={"is_active": True})
        top = [s for s in saved if s.get("confidence") and float(s["confidence"]) >= 0.6][:5]
        if not top:
            return
        for u in users:
            for s in top:
                await notif_service.create(
                    db, u["id"], "signal",
                    f"{s.get('direction')} signal: {s.get('symbol')}",
                    f"{s.get('market', '').title()} · confidence {float(s.get('confidence', 0)) * 100:.0f}% · {s.get('strategy')}",
                    respect_prefs=True,
                )
    except Exception:
        pass