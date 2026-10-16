"""Signal outcome resolution.

Every signal is published with an entry, stop-loss and take-profit. This
service walks *active* signals forward over the OHLC bars that printed after
the signal was created and decides whether price reached the target (TP) or the
stop (SL) first, then closes the signal with an R-multiple. Signals that drift
past ``max_age_hours`` without touching either level are expired.

Runs on the background scheduler tick. Never raises: a failing symbol is
skipped so one bad feed cannot stall the whole batch.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from backend.db.models import SIGNALS
from backend.db.supabase import SupabaseDB, now_iso, parse_dt

log = logging.getLogger("outcomes")

DEFAULT_MAX_AGE_HOURS = 72  # signals older than this expire if untouched
DEFAULT_LIMIT = 5000
# Hard wall-clock budget for a single resolve pass. Bar fetches hit external
# providers synchronously, so without a budget a slow feed could stall the
# scheduler tick indefinitely. The pass stops cleanly and resumes next tick.
# The scheduler interval (15m) leaves ample headroom for a longer pass.
DEFAULT_BUDGET_SECONDS = 240
# Per-symbol bar fetch cap. The underlying providers are synchronous and some
# SDK clients (e.g. Alpaca) have no client-side timeout, so a single stalled
# call could otherwise hang a worker thread forever and stall the whole pass.
DEFAULT_BAR_FETCH_TIMEOUT = 20


def _f(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_utc(dt):
    """Treat naive datetimes as UTC so tz-aware/naive comparisons never raise."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _bar_time(bar: dict) -> datetime | None:
    t = bar.get("time")
    if not t:
        return None
    try:
        return parse_dt(t)
    except (ValueError, TypeError):
        return None


def _bars_for(market: str, symbol: str, outputsize: int = 120) -> list[dict]:
    """Daily OHLC bars (oldest-first) for a symbol. [] when unavailable."""
    try:
        from backend.services import market_service
        data = market_service.get_bars(market, symbol, "1day", outputsize)
        return data.get("bars") or []
    except Exception as e:  # pragma: no cover - defensive
        log.warning("bars fetch failed for %s %s: %s", market, symbol, str(e)[:120])
        return []


def evaluate(direction: str, entry, stop_loss, take_profit,
             bars: list[dict], created_at) -> tuple[str, float] | None:
    """Return (outcome, exit_price) if a level was touched, else None.

    Bars are scanned oldest-first from the signal's creation time. When a single
    bar's range spans both levels we conservatively assume the stop filled first.
    """
    entry = _f(entry)
    sl = _f(stop_loss)
    tp = _f(take_profit)
    if entry is None or sl is None or tp is None or not bars:
        return None

    created = _as_utc(parse_dt(created_at)) if created_at else None
    window = bars
    if created is not None:
        after = [b for b in bars if (_as_utc(_bar_time(b)) or created) >= created]
        window = after or bars[-1:]

    direction = (direction or "").lower()
    for b in window:
        hi = _f(b.get("high"))
        lo = _f(b.get("low"))
        if hi is None or lo is None:
            continue
        if direction == "buy":
            if lo <= sl:
                return "sl", sl
            if hi >= tp:
                return "tp", tp
        else:
            if hi >= sl:
                return "sl", sl
            if lo <= tp:
                return "tp", tp
    return None


def r_multiple(direction: str, entry, stop_loss, exit_price) -> float | None:
    """Risk-reward multiple: how many R the signal made (or lost)."""
    entry = _f(entry)
    sl = _f(stop_loss)
    exit_price = _f(exit_price)
    if entry is None or sl is None or exit_price is None:
        return None
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    if (direction or "").lower() == "buy":
        return round((exit_price - entry) / risk, 4)
    return round((entry - exit_price) / risk, 4)


async def resolve_active_signals(db: SupabaseDB, *, max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
                                 limit: int = DEFAULT_LIMIT,
                                 budget_seconds: int = DEFAULT_BUDGET_SECONDS,
                                 fetch_timeout: int = DEFAULT_BAR_FETCH_TIMEOUT) -> dict:
    """Resolve/expire active signals. Returns counts by outcome.

    Bar feeds are fetched on a worker thread (``asyncio.to_thread``) so the
    synchronous HTTP calls never block the event loop, and the whole pass is
    bounded by ``budget_seconds`` so a slow provider cannot stall the caller.
    """
    try:
        rows = await db.fetch_all(
            SIGNALS,
            where={"status": "active"},
            order="created_at.asc",
            limit=limit,
            columns="id,symbol,market,direction,entry_price,stop_loss,take_profit,created_at",
        )
    except Exception as e:  # pragma: no cover - defensive
        log.warning("resolve_active_signals fetch failed: %s", str(e)[:120])
        return {"tp": 0, "sl": 0, "expired": 0, "skipped": 0, "errors": [str(e)[:150]]}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    counts = {"tp": 0, "sl": 0, "expired": 0, "skipped": 0, "budget_exhausted": False}
    bar_cache: dict[tuple[str, str], list[dict]] = {}
    errors: list[str] = []
    slow: list[dict] = []
    deadline = time.monotonic() + budget_seconds

    for s in rows:
        if time.monotonic() >= deadline:
            counts["budget_exhausted"] = True
            break
        try:
            market = s.get("market")
            symbol = s.get("symbol")
            key = (market, symbol)
            if key not in bar_cache:
                started = time.monotonic()
                try:
                    bar_cache[key] = await asyncio.wait_for(
                        asyncio.to_thread(_bars_for, market, symbol),
                        timeout=fetch_timeout,
                    )
                except Exception:
                    # Stalled provider (incl. asyncio.TimeoutError): treat as no bars.
                    bar_cache[key] = []
                elapsed = time.monotonic() - started
                if elapsed >= 2.0:
                    slow.append({"symbol": symbol, "market": market, "seconds": round(elapsed, 2)})
            bars = bar_cache[key]

            direction = s.get("direction") or ""
            entry = s.get("entry_price")
            sl = s.get("stop_loss")
            tp = s.get("take_profit")
            created = s.get("created_at")

            hit = evaluate(direction, entry, sl, tp, bars, created)
            update: dict | None = None

            if hit:
                outcome, exit_price = hit
                update = {
                    "status": "closed",
                    "outcome": outcome,
                    "exit_price": exit_price,
                    "resolved_at": now_iso(),
                    "r_multiple": r_multiple(direction, entry, sl, exit_price),
                }
            else:
                created_dt = _as_utc(parse_dt(created)) if created else None
                if created_dt is not None and created_dt < cutoff:
                    last = _f(bars[-1].get("close")) if bars else None
                    update = {
                        "status": "expired",
                        "outcome": "expired",
                        "exit_price": last,
                        "resolved_at": now_iso(),
                        "r_multiple": r_multiple(direction, entry, sl, last) if last is not None else None,
                    }
                    outcome = "expired"

            if update is None:
                counts["skipped"] += 1
                continue

            await db.update(SIGNALS, update, where={"id": s["id"]})
            counts[outcome] += 1
        except Exception as e:  # pragma: no cover - defensive
            errors.append(f"{s.get('symbol')}: {str(e)[:100]}")

    if errors:
        counts["errors"] = errors[:10]
    if slow:
        counts["slowest"] = sorted(slow, key=lambda x: x["seconds"], reverse=True)[:8]
    log.info("outcome resolver: %s", {k: v for k, v in counts.items() if k != "errors"})
    return counts


async def outcome_stats(db: SupabaseDB) -> dict:
    """Aggregate resolved-signal hit-rate, overall and per market."""
    # Page through in chunks so aggregates are not silently truncated by
    # PostgREST's 1000-row fetch cap (same fix as get_signal_stats).
    rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        try:
            page = await db.fetch_all(
                SIGNALS,
                where={"status": ["closed", "expired"]},
                columns="market,outcome,r_multiple,data_source",
                order="id.asc",
                limit=page_size,
                offset=offset,
            )
        except Exception as e:
            log.warning("outcome_stats fetch failed: %s", str(e)[:120])
            if not rows:
                return {"resolved": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                        "avg_r": 0.0, "by_outcome": {}, "by_market": {}, "live": 0, "simulated": 0}
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size


    total = wins = 0
    r_sum = 0.0
    r_count = 0
    by_outcome: dict[str, int] = {}
    by_market: dict[str, dict] = {}
    live = simulated = 0

    for r in rows:
        outcome = r.get("outcome")
        if not outcome:
            continue
        market = r.get("market") or "unknown"
        total += 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        m = by_market.setdefault(market, {"resolved": 0, "wins": 0})
        m["resolved"] += 1

        win = outcome == "tp"
        if win:
            wins += 1
            m["wins"] += 1

        rmul = _f(r.get("r_multiple"))
        if rmul is not None:
            r_sum += rmul
            r_count += 1

        src = r.get("data_source")
        if src == "live":
            live += 1
        elif src == "simulated":
            simulated += 1

    markets = []
    for name, m in by_market.items():
        markets.append({
            "market": name,
            "resolved": m["resolved"],
            "wins": m["wins"],
            "win_rate": round(m["wins"] / m["resolved"] * 100, 1) if m["resolved"] else 0.0,
        })
    markets.sort(key=lambda x: x["resolved"], reverse=True)

    return {
        "resolved": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total * 100, 1) if total else 0.0,
        "avg_r": round(r_sum / r_count, 3) if r_count else 0.0,
        "by_outcome": by_outcome,
        "by_market": markets,
        "live": live,
        "simulated": simulated,
    }
