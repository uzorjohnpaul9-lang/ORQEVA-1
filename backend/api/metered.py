"""Phase K: metered public signal API (`/v1`), authenticated by API key.

Requires an `X-API-Key` header (or `Authorization: Bearer <key>`). Responses are
scoped to the key owner's tier - including the Phase J latency window - and each
request is metered against a per-tier daily quota.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.api.signals import _serialize
from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.services import api_key_service, signal_service

router = APIRouter(prefix="/v1", tags=["metered-api"])


def _extract_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _key_auth(db: SupabaseDB, x_api_key: str | None, authorization: str | None) -> dict:
    raw = _extract_key(x_api_key, authorization)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing API key (X-API-Key header)")
    result = await api_key_service.authenticate(db, raw)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    if result.get("error") == "quota_exceeded":
        raise HTTPException(
            status_code=429,
            detail=f"Daily API quota of {result['quota']} requests reached - upgrade your plan",
        )
    return result


@router.get("/signals")
async def v1_signals(
    market: str | None = Query(None),
    status: str | None = Query(None, pattern="^(active|expired|closed)$"),
    limit: int = Query(50, ge=1, le=200),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: SupabaseDB = Depends(get_db),
):
    auth = await _key_auth(db, x_api_key, authorization)
    user = auth["user"]
    signals = await signal_service.list_signals(
        db, market=market, status=status, tier=user.get("tier", "free"), limit=limit
    )
    await api_key_service.record_usage(db, auth["key"])
    return {
        "tier": user.get("tier", "free"),
        "count": len(signals),
        "signals": [_serialize(s) for s in signals],
        "usage": {"used_today": auth["used"] + 1, "daily_quota": auth["quota"]},
    }


@router.get("/usage")
async def v1_usage(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: SupabaseDB = Depends(get_db),
):
    auth = await _key_auth(db, x_api_key, authorization)
    return {
        "tier": auth["user"].get("tier", "free"),
        "daily_quota": auth["quota"],
        "used_today": auth["used"],
        "key_prefix": auth["key"].get("key_prefix"),
    }
