"""Phase K: per-user API keys for the metered `/v1` signal API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import api_key_service

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])

MAX_ACTIVE_KEYS = 10


class KeyCreate(BaseModel):
    name: str | None = Field(default=None, max_length=60)


@router.get("")
async def list_keys(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    keys = await api_key_service.list_keys(db, user["id"])
    return {
        "keys": keys,
        "daily_quota": api_key_service.daily_quota(user.get("tier")),
        "active": sum(1 for k in keys if not k["revoked"]),
    }


@router.post("", status_code=201)
async def create_key(
    body: KeyCreate,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    keys = await api_key_service.list_keys(db, user["id"])
    if sum(1 for k in keys if not k["revoked"]) >= MAX_ACTIVE_KEYS:
        raise HTTPException(status_code=422, detail="Key limit reached - revoke one first")
    return await api_key_service.create_key(db, user["id"], body.name)


@router.delete("/{key_id}")
async def revoke_key(
    key_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    if not await api_key_service.revoke_key(db, user["id"], key_id):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": True}
