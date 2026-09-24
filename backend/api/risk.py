import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user, require_admin
from backend.services import risk_service, telegram_service
from backend.services import notification_service as notif_service
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/risk", tags=["risk"])

# Cross-market engine from the trading system core (kill switch, correlation,
# drawdown auto-trip). Thread-safe; file I/O goes through to_thread.
from risk.central_risk import CentralRiskEngine  # noqa: E402

central = CentralRiskEngine()


class LimitsUpdate(BaseModel):
    max_daily_loss_pct: float | None = Field(default=None, gt=0, le=50)
    max_positions: int | None = Field(default=None, ge=1, le=100)
    max_position_size_pct: float | None = Field(default=None, gt=0, le=100)
    max_daily_trades: int | None = Field(default=None, ge=1, le=200)


class KillSwitchRequest(BaseModel):
    active: bool
    reason: str | None = None


@router.get("/status")
async def risk_status(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    status = await risk_service.get_risk_status(db, user["id"])
    # Cross-market engine summary (shared state across all users' activity)
    status["engine"] = await asyncio.to_thread(central.get_portfolio_summary)
    return status


@router.get("/exposure")
async def risk_exposure(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    status = await risk_service.get_risk_status(db, user["id"])
    return {
        "exposure_by_market": status["exposure_by_market"],
        "total_exposure": status["total_exposure"],
        "exposure_pct": status["exposure_pct"],
        "account_value": status["account_value"],
    }


@router.put("/limits")
async def update_limits(
    body: LimitsUpdate,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    settings = await risk_service.update_limits(
        db, user["id"],
        max_daily_loss_pct=body.max_daily_loss_pct,
        max_positions=body.max_positions,
        max_position_size_pct=body.max_position_size_pct,
        max_daily_trades=body.max_daily_trades,
    )
    return {
        "max_daily_loss_pct": settings.get("max_daily_loss_pct"),
        "max_positions": settings.get("max_positions"),
        "max_position_size_pct": settings.get("max_position_size_pct"),
        "max_daily_trades": settings.get("max_daily_trades"),
    }


@router.post("/kill-switch")
async def kill_switch(
    body: KillSwitchRequest,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))

    if body.active:
        reason = body.reason or f"Manually activated by {user.get('email')}"
        await risk_service.set_kill_switch(db, user["id"], True)
        await asyncio.to_thread(central.activate_kill_switch, reason)
        try:
            await telegram_service.notify_user(
                db, user, "risk",
                f"\U0001f6a8 <b>KILL SWITCH ACTIVATED</b>\nAll new orders blocked.\nReason: {reason}",
            )
        except Exception:
            pass
        await notif_service.create(db, user["id"], "risk", "Kill switch activated", reason)
        return {"kill_switch_active": True, "reason": reason}

    await risk_service.set_kill_switch(db, user["id"], False)
    # Only admins may release the shared engine-level switch
    if user.get("is_admin"):
        await asyncio.to_thread(central.deactivate_kill_switch)
    return {"kill_switch_active": False}


@router.post("/reset-daily")
async def reset_daily(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Admin: reset the central engine's daily counters (e.g. new trading day)."""
    await asyncio.to_thread(central.reset_daily)
    return {"status": "daily counters reset"}