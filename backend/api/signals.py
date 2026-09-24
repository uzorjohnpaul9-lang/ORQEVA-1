import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.db.database import get_db
from backend.db.models import SIGNALS, USERS
from backend.db.schemas import SignalResponse
from backend.db.supabase import SupabaseDB, get_service_client, now_iso, parse_dt
from backend.auth import get_current_user
from backend.config import settings
from backend.services import signal_service
from backend.middleware.rate_limiter import check_rate_limit
from backend.middleware.cache import cache

router = APIRouter(prefix="/api/signals", tags=["signals"])
logger = logging.getLogger(__name__)


def _serialize(signal: dict, with_decay: bool = True) -> dict:
    data = SignalResponse.model_validate(signal).model_dump(mode="json")
    if with_decay:
        eff, age = signal_service.apply_decay(signal.get("confidence"), signal.get("created_at"))
        data["effective_confidence"] = eff
        data["age_hours"] = age
    return data


def _tier_allowed(user: dict, tier_required: str | None) -> bool:
    tier_rank = {"free": 0, "premium": 1, "vip": 2}
    sig_tier = tier_required or "free"
    return (
        user.get("is_admin")
        or sig_tier == "free"
        or (sig_tier == "premium" and tier_rank.get(user.get("tier", "free"), 0) >= 1)
        or (sig_tier == "vip" and user.get("tier") == "vip")
    )


@router.get("/", response_model=None)
async def list_signals(
    market: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))

    cache_key = f"signals:{user.get('tier', 'free')}:{market}:{status}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    signals = await signal_service.list_signals(db, market=market, status=status, tier=user.get("tier", "free"), limit=limit)
    result = [_serialize(s) for s in signals]
    cache.set(cache_key, result, ttl=30)
    return result


@router.get("/stats")
async def signal_stats(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await signal_service.get_signal_stats(db)


@router.get("/accuracy")
async def signal_accuracy(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await signal_service.accuracy_stats(db)


@router.get("/feed")
async def signal_feed(
    request: Request,
    token: str = Query(..., description="JWT (EventSource cannot set headers)"),
):
    """SSE live feed of new signals, gated by the user's tier."""
    # EventSource cannot send Authorization headers, so the JWT comes as a query param.
    from jose import jwt as _jwt, JWTError
    try:
        payload = _jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError
    except (JWTError, ValueError):
        return StreamingResponse(iter(["event: error\ndata: invalid token\n\n"]), media_type="text/event-stream")

    async def event_stream():
        db = SupabaseDB(await get_service_client())
        last_created = now_iso()
        heartbeat = 0
        yield ": connected\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                user = await db.fetch_one(USERS, {"id": user_id})
                if user is None or not user.get("is_active"):
                    yield "event: error\ndata: user inactive\n\n"
                    break

                new_signals = await db.fetch_all(
                    SIGNALS,
                    where={"created_at": {"op": "gt", "value": last_created}},
                    order="created_at.asc",
                    limit=20,
                )

                for s in new_signals:
                    created = parse_dt(s.get("created_at"))
                    last_created_dt = parse_dt(last_created)
                    if created and last_created_dt and created > last_created_dt:
                        last_created = created.isoformat().replace("+00:00", "Z")
                    if not _tier_allowed(user, s.get("tier_required")):
                        continue
                    payload = json.dumps(_serialize(s))
                    yield f"event: signal\ndata: {payload}\n\n"

                heartbeat += 1
                if heartbeat >= 3:  # every ~15s keep the connection alive
                    yield ": ping\n\n"
                    heartbeat = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSE feed error: {e}", exc_info=True)
                yield ": error\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{signal_id}")
async def get_signal_detail(
    signal_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    signal = await signal_service.get_signal(db, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    if not _tier_allowed(user, signal.get("tier_required")):
        raise HTTPException(status_code=403, detail=f"This signal requires {signal.get('tier_required')} tier")

    return _serialize(signal)