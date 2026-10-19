"""Phase K: affiliate partner links (broker / prop-firm) + click tracking."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import get_current_user, require_admin
from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import affiliate_service

router = APIRouter(prefix="/api/affiliates", tags=["affiliates"])
admin_router = APIRouter(prefix="/api/admin/affiliates", tags=["admin-affiliates"])


class PartnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=500)
    category: str = Field(default="broker", pattern="^(broker|prop_firm|partner)$")


class ActiveToggle(BaseModel):
    active: bool


@router.get("")
async def list_affiliates(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {"partners": await affiliate_service.list_partners(db)}


@router.post("/{partner_id}/click")
async def track_click(
    partner_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    partner = await affiliate_service.record_click(db, partner_id, user["id"])
    if partner is None:
        raise HTTPException(status_code=404, detail="Unknown partner")
    return {"partner": partner}


@admin_router.get("")
async def admin_list_affiliates(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {
        "partners": await affiliate_service.admin_list_partners(db),
        "summary": await affiliate_service.summary(db),
    }


@admin_router.post("", status_code=201)
async def admin_create_affiliate(
    body: PartnerCreate,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    created = await affiliate_service.create_partner(
        db, name=body.name, url=body.url, category=body.category
    )
    if created.get("error"):
        raise HTTPException(status_code=422, detail=created["error"])
    return created


@admin_router.post("/{partner_id}/toggle")
async def admin_toggle_affiliate(
    partner_id: str,
    body: ActiveToggle,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    updated = await affiliate_service.set_partner_active(db, partner_id, body.active)
    if updated is None:
        raise HTTPException(status_code=404, detail="Unknown partner")
    return updated
