"""Engine scan orchestration shared by the admin endpoint and the background scheduler."""
import asyncio
import logging
import os
from typing import Any

from backend.db.models import SIGNALS, USERS
from backend.db.supabase import SupabaseDB, now_iso
from backend.services import signal_service, signal_terms
from engines.price_levels import round_price, valid_levels

log = logging.getLogger(__name__)

# (bucket, module, class, strategy, tier, db_market, term, timeframe)
# bucket = result grouping; db_market = value stored in signals.market
_ENGINE_SPECS = [
    ("stock", "engines.stock_engine", "StockEngine", "Alpaca Breakout", "premium", "stock", "very_long", "1day"),
    ("forex", "engines.forex_engine", "ForexEngine", "Twelve Data Trend", "free", "forex", "very_long", "1day"),
    ("crypto", "engines.crypto_engine", "CryptoEngine", "Crypto Momentum", "vip", "crypto", "very_long", "1day"),
    ("crypto_alt", "engines.crypto_alt_engine", "CryptoAltEngine", "Meme Momentum", "vip", "crypto", "very_long", "1day"),
    ("commodity", "engines.commodity_engine", "CommodityEngine", "Commodity Trend", "premium", "commodity", "very_long", "1day"),
]

_FAST_SYMBOL_DEFAULTS = {
    "crypto": ["BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD"],
    "forex": ["EUR/USD"],
    "commodity": ["XAU/USD"],
}


def _empty_results() -> dict[str, list]:
    return {"stock": [], "forex": [], "crypto": [], "crypto_alt": [], "commodity": []}


def _engine_signal_to_db(signal, market: str, strategy: str, tier: str = "free",
                         event_context: dict | None = None,
                         term: str = signal_terms.DEFAULT_TERM,
                         timeframe: str | None = None) -> dict:
    indicators = dict(signal.metadata or {})
    data_source = indicators.pop("data_source", None) or "live"
    if event_context:
        indicators["event_context"] = event_context
    # Engines emit "BUY"/"SELL"; rows are stored lowercased, so normalise
    # here too - otherwise the cooldown lookup never matches the stored
    # signal and the same call gets published over and over.
    direction = str(signal.direction or "").lower()
    entry = round_price(signal.price)
    stop_loss = round_price(signal.stop_loss)
    take_profit = round_price(signal.target_price)
    if not valid_levels(direction, entry, stop_loss, take_profit):
        raise ValueError(
            f"invalid levels for {signal.symbol}: entry={entry} "
            f"sl={stop_loss} tp={take_profit}"
        )
    term = signal_terms.normalize_term(getattr(signal, "term", None) or term)
    timeframe = (
        getattr(signal, "timeframe", None) or timeframe
        or signal_terms.data_interval(term)
    )
    return {
        "symbol": signal.symbol,
        "market": market,
        "direction": direction,
        "confidence": round(signal.confidence, 4),
        "entry_price": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "strategy": (signal.metadata or {}).get("strategy") or strategy,
        "tier": tier,
        "indicators": indicators,
        "data_source": data_source,
        "term": term,
        "timeframe": timeframe,
        "resolution_interval": signal_terms.resolver_interval(term),
    }


async def recent_signal_keys(
    db: SupabaseDB, hours: int, symbols: list[str] | None = None,
    term_cooldowns: dict[str, float] | None = None,
    include_term: bool = False,
) -> set[tuple]:
    """Keys still blocking a re-issue.

    Expired and cancelled rows, plus active rows whose confidence has already
    decayed below the validity floor, do not block a fresh signal. That lets the
    scanner replace an invalid setup immediately instead of waiting out the
    cooldown. ``symbols`` narrows the query server-side. Without it PostgREST's
    1000-row cap silently truncates the window - a busy table has thousands of
    rows in 24h - so the cooldown misses signals and duplicates get published.
    The rows are paged through for the same reason.

    ``term_cooldowns`` applies a per-term window (fast terms cooldown in
    minutes). ``include_term`` returns (symbol, market, direction, term) so a
    fast scalp does not suppress a swing call on the same pair.
    """
    from datetime import datetime, timedelta, timezone

    if symbols is not None and not symbols:
        return set()

    max_hours = max([float(hours or 0), *(term_cooldowns or {}).values()])
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_hours)).isoformat().replace("+00:00", "Z")
    where: dict[str, Any] = {"created_at": {"op": "gte", "value": cutoff}}
    if symbols is not None:
        where["symbol"] = sorted(set(symbols))

    rows: list[dict] = []
    page_size = 1000
    offset = 0
    columns = "symbol,market,direction,status,confidence,created_at,term"
    while True:
        try:
            chunk = await db.fetch_all(
                SIGNALS,
                where=where,
                columns=columns,
                limit=page_size,
                offset=offset,
            )
        except Exception:
            if "term" not in columns:
                raise
            # The term migration has not been applied yet; legacy columns only.
            columns = "symbol,market,direction,status,confidence,created_at"
            continue
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size

    def _blocks_reissue(row: dict) -> bool:
        status = (row.get("status") or "active").lower()
        if status in ("expired", "cancelled"):
            return False
        term = signal_terms.normalize_term(row.get("term"))
        window = (term_cooldowns or {}).get(term, hours)
        if window and window > 0:
            try:
                created = datetime.fromisoformat(str(row.get("created_at")).replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - created).total_seconds() / 3600 > window:
                    return False
            except (TypeError, ValueError):
                pass
        confidence = row.get("confidence")
        if status == "active" and confidence is not None:
            return signal_service.is_signal_valid(confidence, row.get("created_at"), term=term)
        return True

    keys = []
    for r in rows:
        if not _blocks_reissue(r):
            continue
        base = (r.get("symbol"), r.get("market"), r.get("direction"))
        if include_term:
            base = base + (signal_terms.normalize_term(r.get("term")),)
        keys.append(base)
    return set(keys)


async def run_scan(db: SupabaseDB, *, cooldown_hours: int = 0) -> dict:
    """Run all engines once, save new signals, fan out notifications.

    Returns {"signals_generated", "by_market", "errors", "saved"}.
    """
    results: dict[str, list] = _empty_results()
    errors: list[str] = []
    dropped_invalid = 0

    try:
        from backend.services import calendar_service
        event_context = calendar_service.event_context()
    except Exception:
        event_context = None

    for bucket, mod_name, cls_name, strategy, tier, db_market, term, timeframe in _ENGINE_SPECS:
        try:
            module = __import__(mod_name, fromlist=[cls_name])
            engine = getattr(module, cls_name)()
            if await asyncio.to_thread(engine.is_market_hours):
                raw = await asyncio.to_thread(engine.run_cycle)
                for signal in raw:
                    try:
                        row = _engine_signal_to_db(
                            signal, db_market, strategy, tier, event_context,
                            term=term, timeframe=timeframe,
                        )
                    except ValueError as e:
                        dropped_invalid += 1
                        log.warning("dropped invalid signal: %s", e)
                        continue
                    results[bucket].append(row)
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
        "dropped_invalid": dropped_invalid,
        "errors": errors,
        "saved": saved,
    }


async def run_fast_scan(db: SupabaseDB) -> dict:
    """Run the 1m/5m fast lane once and publish VIP-only scalps.

    Fast terms are deliberately separated from the swing scan: they use short
    TTL bars, a cost-aware take-profit gate and per-term cooldowns. If the
    fast lane errors it must never take the main scan down with it.
    """
    from engines.intraday_engine import IntradayEngine

    terms_raw = os.getenv("FAST_SCAN_TERMS", ",".join(signal_terms.FAST_TERMS))
    terms = []
    for raw in terms_raw.split(","):
        if signal_terms.is_valid_term(raw) and signal_terms.is_fast(raw):
            term = signal_terms.normalize_term(raw)
            if term not in terms:
                terms.append(term)

    errors: list[str] = []
    rows: list[dict] = []
    dropped_invalid = 0

    for term in terms:
        for market, default_symbols in _FAST_SYMBOL_DEFAULTS.items():
            env_symbols = os.getenv(f"FAST_SCAN_{market.upper()}_SYMBOLS")
            symbols = (
                [s.strip() for s in env_symbols.split(",") if s.strip()]
                if env_symbols else default_symbols
            )
            if not symbols:
                continue
            try:
                engine = IntradayEngine(market=market, symbols=symbols, term=term)
                if not await asyncio.to_thread(engine.is_market_hours):
                    continue
                raw_signals = await asyncio.to_thread(engine.run_cycle)
                for signal in raw_signals:
                    try:
                        rows.append(_engine_signal_to_db(
                            signal, market, f"Fast {signal_terms.label(term)}",
                            signal_terms.min_tier(term), None,
                            term=term, timeframe=signal_terms.data_interval(term),
                        ))
                    except ValueError as e:
                        dropped_invalid += 1
                        log.warning("dropped invalid fast signal: %s", e)
            except Exception as e:
                errors.append(f"fast {term} {market}: {str(e)[:150]}")

    if rows:
        symbols = sorted({r["symbol"] for r in rows})
        seen = await recent_signal_keys(
            db,
            hours=0,
            symbols=symbols,
            term_cooldowns={t: signal_terms.cooldown_hours(t) for t in terms},
            include_term=True,
        )
        rows = [
            r for r in rows
            if (r["symbol"], r["market"], r["direction"], r["term"]) not in seen
        ]

    dropped_simulated = sum(1 for r in rows if r.get("data_source") != "live")
    rows = [r for r in rows if r.get("data_source") == "live"]

    cap = max(1, int(os.getenv("FAST_MAX_SIGNALS_PER_SCAN", "6")))
    dropped_capped = max(0, len(rows) - cap)
    rows = rows[:cap]

    saved: list[dict] = []
    if rows:
        saved = await signal_service.save_signals_batch(db, rows)
        await _auto_trade(db, saved, errors)
        fresh = {"fast": saved}
        await _fan_out(db, fresh, saved, errors)

    from backend.middleware.cache import cache
    cache.clear()

    return {
        "signals_generated": len(saved),
        "terms": terms,
        "symbols": sorted({r["symbol"] for r in rows}),
        "by_market": {
            market: sum(1 for r in rows if r["market"] == market)
            for market in _FAST_SYMBOL_DEFAULTS
        },
        "dropped_simulated": dropped_simulated,
        "dropped_invalid": dropped_invalid,
        "dropped_capped": dropped_capped,
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