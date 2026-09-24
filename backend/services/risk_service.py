from datetime import datetime, timezone

from backend.db.models import TRADES, RISK_SETTINGS, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso, parse_dt


async def get_or_create_settings(db: SupabaseDB, user_id: str) -> dict:
    settings = await db.fetch_one(RISK_SETTINGS, {"user_id": user_id})
    if settings is None:
        settings = {
            "id": gen_uuid(),
            "user_id": user_id,
            "max_daily_loss_pct": 5.0,
            "max_positions": 10,
            "max_position_size_pct": 10.0,
            "max_daily_trades": 20,
            "kill_switch_active": False,
            "updated_at": now_iso(),
            "last_checked": None,
        }
        try:
            settings = await db.insert(RISK_SETTINGS, settings)
        except Exception:
            # Concurrent create raced; fall back to reading the winner.
            winner = await db.fetch_one(RISK_SETTINGS, {"user_id": user_id})
            if winner:
                settings = winner
    return settings


def _utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_risk_status(db: SupabaseDB, user_id: str) -> dict:
    """User-level risk metrics computed from their trades + settings."""
    settings = await get_or_create_settings(db, user_id)

    closed = await db.fetch_all(
        TRADES, where={"user_id": user_id, "status": "closed"}, columns="id,pnl,closed_at"
    )
    realized = sum(float(r.get("pnl") or 0) for r in closed)
    account_value = 100000.0 + realized

    day_start = _utc_day_start()
    today_closed = [r for r in closed if parse_dt(r.get("closed_at")) and parse_dt(r["closed_at"]) >= day_start]
    daily_pnl = sum(float(r.get("pnl") or 0) for r in today_closed)

    opened_today = await db.fetch_all(
        TRADES,
        where={"user_id": user_id, "opened_at": {"op": "gte", "value": day_start.isoformat().replace("+00:00", "Z")}},
        columns="id",
    )
    trades_today = len(opened_today)

    open_trades = await db.fetch_all(TRADES, where={"user_id": user_id, "status": "open"})
    exposure_by_market: dict[str, float] = {}
    for t in open_trades:
        mkt = t.get("market") or "other"
        exposure_by_market[mkt] = exposure_by_market.get(mkt, 0.0) + abs(float(t["quantity"]) * float(t["entry_price"]))
    total_exposure = sum(exposure_by_market.values())

    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in sorted(closed, key=lambda r: parse_dt(r.get("closed_at")) or datetime.min.replace(tzinfo=timezone.utc)):
        p = float(r.get("pnl") or 0)
        cum += p
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    max_daily_loss_usd = account_value * (float(settings.get("max_daily_loss_pct", 5)) / 100.0)
    daily_loss_used_pct = (
        min(abs(min(daily_pnl, 0.0)) / max_daily_loss_usd * 100.0, 999.0)
        if max_daily_loss_usd > 0 else 0.0
    )
    exposure_pct = total_exposure / account_value * 100.0 if account_value else 0.0
    max_daily_trades = int(settings.get("max_daily_trades") or 20)
    max_positions = int(settings.get("max_positions") or 10)
    trades_limit_used_pct = trades_today / max_daily_trades * 100.0 if max_daily_trades else 0.0

    score = "low"
    if (
        daily_loss_used_pct >= 80
        or exposure_pct > 60
        or len(open_trades) >= max_positions
        or trades_limit_used_pct >= 100
    ):
        score = "high"
    elif (
        daily_loss_used_pct >= 50
        or exposure_pct > 35
        or len(open_trades) >= max(max_positions - 2, 1)
        or trades_limit_used_pct >= 80
    ):
        score = "medium"

    return {
        "account_value": round(account_value, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_loss_limit": round(max_daily_loss_usd, 2),
        "daily_loss_used_pct": round(daily_loss_used_pct, 1),
        "trades_today": trades_today,
        "max_daily_trades": max_daily_trades,
        "open_positions": len(open_trades),
        "max_positions": max_positions,
        "total_exposure": round(total_exposure, 2),
        "exposure_pct": round(exposure_pct, 1),
        "exposure_by_market": {k: round(v, 2) for k, v in sorted(exposure_by_market.items(), key=lambda kv: -kv[1])},
        "max_drawdown": round(max_dd, 2),
        "kill_switch_active": bool(settings.get("kill_switch_active")),
        "risk_score": score,
        "limits": {
            "max_daily_loss_pct": settings.get("max_daily_loss_pct", 5.0),
            "max_positions": max_positions,
            "max_position_size_pct": settings.get("max_position_size_pct", 10.0),
            "max_daily_trades": max_daily_trades,
        },
    }


async def pre_trade_check(db: SupabaseDB, user_id: str, market: str,
                          quantity: float, price: float) -> tuple[bool, str]:
    """Gate for placing new orders. Returns (allowed, reason)."""
    status = await get_risk_status(db, user_id)

    if status["kill_switch_active"]:
        return False, "Kill switch is active - close positions or disable it first"

    if status["open_positions"] >= status["max_positions"]:
        return False, f"Max positions reached ({status['max_positions']})"

    if status["daily_loss_used_pct"] >= 100:
        return False, f"Daily loss limit hit (${status['daily_loss_limit']})"

    if status["trades_today"] >= status["max_daily_trades"]:
        return False, f"Daily trade limit reached ({status['max_daily_trades']} trades today)"

    notional = quantity * price
    pos_size_pct = notional / status["account_value"] * 100 if status["account_value"] else 0
    if pos_size_pct > status["limits"]["max_position_size_pct"]:
        return False, (
            f"Position size {pos_size_pct:.1f}% exceeds "
            f"{status['limits']['max_position_size_pct']}% limit"
        )

    projected_exposure_pct = (status["total_exposure"] + notional) / status["account_value"] * 100 \
        if status["account_value"] else 0
    if projected_exposure_pct > 80:
        return False, f"Total exposure would reach {projected_exposure_pct:.0f}% of account"

    return True, "OK"


async def update_limits(db: SupabaseDB, user_id: str,
                        max_daily_loss_pct: float | None = None,
                        max_positions: int | None = None,
                        max_position_size_pct: float | None = None,
                        max_daily_trades: int | None = None) -> dict:
    settings = await get_or_create_settings(db, user_id)
    changes: dict = {"updated_at": now_iso()}
    if max_daily_loss_pct is not None:
        changes["max_daily_loss_pct"] = max(0.1, min(max_daily_loss_pct, 50.0))
    if max_positions is not None:
        changes["max_positions"] = max(1, min(max_positions, 100))
    if max_position_size_pct is not None:
        changes["max_position_size_pct"] = max(0.5, min(max_position_size_pct, 100.0))
    if max_daily_trades is not None:
        changes["max_daily_trades"] = max(1, min(max_daily_trades, 200))
    updated = await db.update(RISK_SETTINGS, changes, where={"user_id": user_id})
    if updated:
        return updated[0]
    return settings


async def set_kill_switch(db: SupabaseDB, user_id: str, active: bool) -> dict:
    settings = await get_or_create_settings(db, user_id)
    updated = await db.update(RISK_SETTINGS, {"kill_switch_active": active, "updated_at": now_iso()}, where={"user_id": user_id})
    if updated:
        return updated[0]
    return settings