"""AI Auto-Trade (Phase 16): the engine's signals auto-place orders for opted-in users.

Runs inside :func:`backend.services.engine_service.run_scan` after signals are saved,
so it fires both on the 15-minute schedule and on an admin-triggered scan. Every attempt
is written to :ref:`auto_trade_log` (UNIQUE(user_id, signal_id) keeps re-scans harmless).

Flow per signal x user: tier gate -> market enabled -> confidence -> dedupe ->
route (live needs a validated connection, never silent paper fallback) ->
user risk pre-check -> central engine gate -> risk-per-trade sizing -> place -> ledger.
"""
import asyncio

from backend.db.models import (
    USERS,
    AUTO_TRADE_LOG,
    AUTO_TRADE_SETTINGS,
    gen_uuid,
)
from backend.db.supabase import SupabaseDB, now_iso
from backend.db.schemas import AutoTradeSettings
from backend.services import notification_service as notif_service
from backend.services import risk_service
from backend.services import telegram_service
from backend.services.order_executor import active_connection, live_price, place_and_record
from backend.api.risk import central

# Market -> minimum tier that may auto-trade (mirrors engine_service._ENGINE_SPECS).
_MARKET_MIN_TIER = {"stock": "premium", "forex": "free", "crypto": "vip"}
_TIER_RANK = {"free": 0, "premium": 1, "vip": 2}

MARKETS = ["stock", "forex", "crypto"]


async def get_or_create_settings(db: SupabaseDB, user_id: str) -> dict:
    settings = await db.fetch_one(AUTO_TRADE_SETTINGS, {"user_id": user_id})
    if settings is not None:
        return settings
    defaults = AutoTradeSettings().model_dump()
    try:
        settings = await db.insert(AUTO_TRADE_SETTINGS, {
            "id": gen_uuid(),
            "user_id": user_id,
            "enabled": defaults["enabled"],
            "route": defaults["route"],
            "markets": defaults["markets"],
            "per_trade_risk_pct": defaults["per_trade_risk_pct"],
            "min_confidence": defaults["min_confidence"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        return settings
    except Exception:
        winner = await db.fetch_one(AUTO_TRADE_SETTINGS, {"user_id": user_id})
        if winner:
            return winner
        return {**defaults, "user_id": user_id}


async def update_settings(db: SupabaseDB, user_id: str, data: AutoTradeSettings) -> dict:
    current = await get_or_create_settings(db, user_id)
    markets = [m for m in data.markets if m in MARKETS] or MARKETS
    changes = {
        "enabled": data.enabled,
        "route": data.route,
        "markets": markets,
        "per_trade_risk_pct": data.per_trade_risk_pct,
        "min_confidence": data.min_confidence,
        "updated_at": now_iso(),
    }
    try:
        updated = await db.update(AUTO_TRADE_SETTINGS, changes, where={"user_id": user_id})
        if updated:
            return updated[0]
    except Exception:
        pass
    return {**current, **changes}


def _view_settings(s: dict) -> dict:
    markets = s.get("markets") or MARKETS
    if not isinstance(markets, list):
        try:
            import json
            markets = json.loads(markets) or MARKETS
        except Exception:
            markets = MARKETS
    return {
        "enabled": bool(s.get("enabled")),
        "route": s.get("route") or "paper",
        "markets": [m for m in markets if m in MARKETS],
        "per_trade_risk_pct": float(s.get("per_trade_risk_pct") or 1.0),
        "min_confidence": float(s.get("min_confidence") or 0.0),
        "updated_at": s.get("updated_at"),
    }


def _tier_allows(tier: str | None, market: str) -> bool:
    if market not in _MARKET_MIN_TIER:
        return False
    return _TIER_RANK.get(tier or "free", 0) >= _TIER_RANK[_MARKET_MIN_TIER[market]]


def _size_trade(signal: dict, account_value: float, risk_pct: float, max_pos_pct: float) -> float | None:
    """Risk-per-trade sizing with a notional cap. Returns quantity or None."""
    price = signal.get("entry_price")
    if not price or float(price) <= 0:
        return None
    price = float(price)
    risk_amount = account_value * (float(risk_pct or 1.0) / 100.0)
    stop = signal.get("stop_loss")
    distance = abs(price - float(stop)) if stop and float(stop) > 0 else 0.0
    if distance > 0:
        qty = risk_amount / distance
    else:
        qty = account_value * (float(max_pos_pct or 10.0) / 100.0) / price
    max_notional_qty = account_value * (float(max_pos_pct or 10.0) / 100.0) / price
    qty = min(qty, max_notional_qty)
    return round(max(qty, 0.0), 6) if qty > 0 else None


async def _log(db: SupabaseDB, *, user_id: str, signal: dict, status: str,
               quantity: float | None = None, entry_price: float | None = None,
               route: str = "paper", reason: str | None = None,
               trade_id: str | None = None) -> None:
    try:
        await db.insert(AUTO_TRADE_LOG, {
            "id": gen_uuid(),
            "user_id": user_id,
            "signal_id": signal.get("id"),
            "symbol": signal.get("symbol"),
            "market": signal.get("market"),
            "direction": (signal.get("direction") or "buy").lower(),
            "confidence": signal.get("confidence"),
            "quantity": quantity,
            "entry_price": entry_price,
            "route": route,
            "status": status,
            "reason": reason[:400] if reason else None,
            "trade_id": trade_id,
            "created_at": now_iso(),
        })
    except Exception:
        # UNIQUE(user_id, signal_id) collision - another runner already logged this signal.
        pass


async def execute_for_signal(db: SupabaseDB, signal: dict, settings_rows: list[dict],
                             users_by_id: dict[str, dict]) -> None:
    """Evaluate one newly-saved signal against every enabled user's settings."""
    price = signal.get("entry_price")
    for s in settings_rows:
        user = users_by_id.get(s.get("user_id"))
        if not user or not user.get("is_active"):
            continue

        try:
            # Tier gate (auto-trade mirrors the same tier ladder as the engines).
            market = signal.get("market")
            if not _tier_allows(user.get("tier"), market):
                continue

            # Market enabled + confidence gate.
            if market not in s.get("markets", MARKETS):
                continue
            conf = float(signal.get("confidence") or 0)
            if conf < float(s.get("min_confidence") or 0):
                continue

            # Dedupe: a prior scan that placed/skipped/rejected this signal is authoritative.
            existing = await db.fetch_one(
                AUTO_TRADE_LOG, {"user_id": s["user_id"], "signal_id": signal.get("id")}
            )
            if existing:
                continue

            route = s.get("route") or "paper"
            conn = None
            if route == "live":
                conn = await active_connection(db, s["user_id"], market)
                if not conn:
                    await _log(db, user_id=s["user_id"], signal=signal, status="skipped",
                               route=route, reason=f"no validated live {market} connection")
                    continue

            # Price: use the signal's entry price, fall back to a live quote.
            if not price or float(price) <= 0:
                live = await live_price(market, signal.get("symbol"))
                if not live or live <= 0:
                    await _log(db, user_id=s["user_id"], signal=signal, status="error",
                               route=route, reason="price unavailable")
                    continue
                price = f"{live:.8f}"

            # Size from risk-per-trade %, capped by the user's max position %.
            status = await risk_service.get_risk_status(db, s["user_id"])
            account_value = float(status.get("account_value") or 0)
            pos_size_pct = status.get("limits", {}).get("max_position_size_pct", 10.0)
            qty = _size_trade(signal, account_value, s.get("per_trade_risk_pct"), pos_size_pct)
            if not qty:
                await _log(db, user_id=s["user_id"], signal=signal, status="skipped",
                           route=route, reason="could not size position from signal")
                continue

            # User-level risk gate (kill switch, position/trade counts, exposure).
            allowed, reason = await risk_service.pre_trade_check(
                db, s["user_id"], market, qty, float(price)
            )
            if not allowed:
                await _log(db, user_id=s["user_id"], signal=signal, status="rejected",
                           quantity=qty, entry_price=float(price), route=route, reason=reason)
                continue

            # Central engine (cross-market kill switch, drawdown, correlation).
            decision = await asyncio.to_thread(
                central.approve_trade, market, signal.get("symbol"),
                (signal.get("direction") or "buy").upper(), qty, float(price), account_value
            )
            if not getattr(decision, "allowed", False):
                await _log(db, user_id=s["user_id"], signal=signal, status="skipped",
                           quantity=qty, entry_price=float(price), route=route,
                           reason=getattr(decision, "reason", "central risk gate"))
                continue

            result = await place_and_record(
                db, user=user, symbol=signal.get("symbol"), market=market,
                side=(signal.get("direction") or "buy"), quantity=qty,
                entry_price=float(price), route=route, conn=conn,
                stop_loss=signal.get("stop_loss"), take_profit=signal.get("take_profit"),
                strategy=f"auto:{signal.get('strategy') or 'ai'}", signal_id=signal.get("id"),
            )
            if result.get("status") != "filled":
                await _log(db, user_id=s["user_id"], signal=signal, status="error",
                           quantity=qty, entry_price=float(price), route=route,
                           reason=result.get("detail") or "order failed")
                continue

            await _log(db, user_id=s["user_id"], signal=signal, status="placed",
                       quantity=qty, entry_price=float(price), route=route,
                       reason="ok", trade_id=result.get("trade_id"))
            await _notify(db, user, signal, result, route)
        except Exception as e:  # never let one user's failure break the scan
            await _log(db, user_id=s["user_id"], signal=signal, status="error",
                       route=s.get("route") or "paper", reason=f"auto-trade error: {str(e)[:300]}")


async def _notify(db: SupabaseDB, user: dict, signal: dict, result: dict, route: str) -> None:
    desc = f"{signal.get('symbol')} {signal.get('direction')} @ {result.get('entry_price')}"
    try:
        await notif_service.create(
            db, user["id"], "auto_trade",
            f"Auto order placed: {desc}",
            f"{route} route · {signal.get('strategy')} · via {result.get('venue') or 'paper'}",
        )
        await telegram_service.notify_user(
            db, user, "signals",
            f"\u2699\ufe0f <b>AI order placed</b>\n{desc}\nRoute: {route}",
        )
    except Exception:
        pass


async def run_for_scan(db: SupabaseDB, saved_signals: list[dict]) -> dict:
    """Called after signals are saved by run_scan. Returns per-status attempt counts."""
    counts = {"placed": 0, "skipped": 0, "rejected": 0, "error": 0}
    if not saved_signals:
        return counts

    settings_rows = await db.fetch_all(AUTO_TRADE_SETTINGS, where={"enabled": True})
    if not settings_rows:
        return counts
    user_ids = list({r["user_id"] for r in settings_rows})
    users = await db.fetch_all(USERS, where={"id": user_ids})
    users_by_id = {u["id"]: u for u in users}

    refresh_counts = dict(counts)
    for signal in saved_signals:
        before = await db.count(AUTO_TRADE_LOG, where={"signal_id": signal.get("id")})
        await execute_for_signal(db, signal, settings_rows, users_by_id)
        rows = await db.fetch_all(AUTO_TRADE_LOG, where={"signal_id": signal.get("id")},
                                  order="created_at.asc")
        for row in rows[before:]:
            status = row.get("status")
            if status in refresh_counts:
                refresh_counts[status] += 1
    return refresh_counts