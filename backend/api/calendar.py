import asyncio

from fastapi import APIRouter, Depends, Query

from backend.auth import get_current_user
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import calendar_service

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


async def _offload(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


@router.get("/status")
async def calendar_status(user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return calendar_service.status()


@router.get("/upcoming")
async def calendar_upcoming(
    days: int = Query(7, ge=1, le=92),
    impact: str | None = Query(None, description="high | medium | low"),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    events = await _offload(calendar_service.upcoming, days, impact)
    return {"events": events, "attribution": calendar_service.ATTRIBUTION}


@router.get("/today")
async def calendar_today(user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    events = await _offload(calendar_service.today)
    return {"events": events, "attribution": calendar_service.ATTRIBUTION}


@router.get("/next")
async def calendar_next(
    series: str | None = Query(None, description="fomc | cpi | jobs | gdp | ecb | ..."),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await _offload(calendar_service.next_events, series)


@router.get("/active")
async def calendar_active(
    window_minutes: int = Query(30, ge=1, le=720),
    user: dict = Depends(get_current_user),
):
    """High-impact events inside the guard window (for the in-app banner)."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    events = await _offload(calendar_service.high_impact_soon, window_minutes)
    return {
        "events": events,
        "affected_markets": sorted(calendar_service.affected_markets(window_minutes)),
        "attribution": calendar_service.ATTRIBUTION,
    }
