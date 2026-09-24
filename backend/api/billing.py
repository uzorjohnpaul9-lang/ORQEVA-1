from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.db.database import get_db
from backend.db.models import USERS
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user, require_admin
from backend.services import billing_service as billing
from backend.services import telegram_service
from backend.services import notification_service as notif_service
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/billing", tags=["billing"])


class InvoiceCreate(BaseModel):
    tier: str = Field(pattern="^(premium|vip)$")
    method: str = Field(default="crypto", pattern="^(crypto|manual)$")
    promo_code: str | None = Field(default=None, max_length=40)


class TxRefSubmit(BaseModel):
    tx_ref: str = Field(min_length=4, max_length=500)


class AutoRenew(BaseModel):
    enabled: bool


class PromoCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    discount_pct: float = Field(gt=0, le=100)
    max_uses: int = Field(default=100, ge=1, le=100000)
    expires_days: int | None = Field(default=None, ge=1, le=3650)


class ProcessReason(BaseModel):
    reason: str = Field(default="", max_length=300)


# ---- Plans / subscription (user) ----

@router.get("/plans")
async def get_plans(user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {"plans": billing.plans(), "current_tier": user.get("tier")}


@router.get("/subscription")
async def my_subscription(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    sub = await billing.get_subscription(db, user["id"])
    if not sub:
        return {"tier": user.get("tier"), "status": "none", "auto_renew": False,
                "days_left": 0, "lifetime_spend_usd": 0.0}
    return sub


@router.post("/subscription/auto-renew")
async def toggle_auto_renew(
    body: AutoRenew,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    ok = await billing.set_auto_renew(db, user["id"], body.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="no subscription")
    return {"auto_renew": body.enabled}


# ---- Invoices (user) ----

@router.post("/invoices", status_code=201)
async def create_invoice(
    body: InvoiceCreate,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    inv = await billing.create_invoice(db, user, body.tier, body.method, body.promo_code)
    if inv.get("error"):
        raise HTTPException(status_code=422, detail=inv["error"])
    return billing.invoice_view(inv)


async def _own_invoice_or_404(db: SupabaseDB, invoice_id: str, user_id: str | None = None) -> dict:
    inv = await billing.get_owned_invoice(db, invoice_id, user_id)
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    return inv


@router.get("/invoices")
async def my_invoices(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    from backend.db.models import INVOICES
    res = await db.fetch_all(INVOICES, where={"user_id": user["id"]}, order="created_at.desc", limit=50)
    return [billing.invoice_view(i) for i in res]


@router.post("/invoices/{invoice_id}/tx-ref")
async def submit_payment_proof(
    invoice_id: str,
    body: TxRefSubmit,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    inv = await _own_invoice_or_404(db, invoice_id, user["id"])
    if inv.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"invoice already {inv.get('status')}")
    inv = await billing.submit_tx_ref(db, inv, body.tx_ref)
    return billing.invoice_view(inv)


@router.post("/invoices/{invoice_id}/cancel")
async def cancel_my_invoice(
    invoice_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    inv = await _own_invoice_or_404(db, invoice_id, user["id"])
    if inv.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"invoice already {inv.get('status')}")
    inv = await billing.cancel_invoice(db, inv)
    return billing.invoice_view(inv)


# ---- Admin ----

@router.get("/admin/invoices")
async def admin_invoices(
    status: str | None = Query(None, pattern="^(pending|approved|rejected|refunded|cancelled)$"),
    limit: int = Query(100, ge=1, le=500),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await billing.admin_list_invoices(db, status, limit)


async def _notify_owner(db: SupabaseDB, inv: dict, text: str, title: str = "Billing update"):
    try:
        owner = await db.fetch_one(USERS, {"id": inv["user_id"]})
        if owner:
            await telegram_service.notify_user(db, owner, "system", text)
            await notif_service.create(
                db, inv["user_id"], "system", title,
                text.replace("<b>", "").replace("</b>", "").replace("\n", " ")[:200],
                respect_prefs=True,
            )
    except Exception:
        pass


@router.post("/admin/invoices/{invoice_id}/approve")
async def approve(
    invoice_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    inv = await _own_invoice_or_404(db, invoice_id)
    out = await billing.approve_invoice(db, inv, user)
    if out.get("error"):
        raise HTTPException(status_code=400, detail=out["error"])
    await _notify_owner(
        db, out,
        f"\U0001f389 <b>Subscription active</b>\nYour {out.get('tier', '').upper()} plan is now live. Thank you!",
        title="Subscription activated",
    )
    return billing.invoice_view(out)


@router.post("/admin/invoices/{invoice_id}/reject")
async def reject(
    invoice_id: str,
    body: ProcessReason | None = None,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    inv = await _own_invoice_or_404(db, invoice_id)
    out = await billing.reject_invoice(db, inv, user, body.reason if body else "")
    if out.get("error"):
        raise HTTPException(status_code=400, detail=out["error"])
    await _notify_owner(
        db, out,
        f"\u26a0\ufe0f <b>Payment rejected</b>\nInvoice {out.get('id', '')[:8]} could not be verified."
        + (f" Reason: {out.get('note')}" if out.get("note") else ""),
        title="Payment rejected",
    )
    return billing.invoice_view(out)


@router.post("/admin/invoices/{invoice_id}/refund")
async def refund(
    invoice_id: str,
    body: ProcessReason | None = None,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    inv = await _own_invoice_or_404(db, invoice_id)
    out = await billing.refund_invoice(db, inv, user, body.reason if body else "")
    if out.get("error"):
        raise HTTPException(status_code=400, detail=out["error"])
    await _notify_owner(
        db, out,
        f"\U0001f4b8 <b>Subscription refunded</b>\nInvoice {out.get('id', '')[:8]} refunded; your plan was downgraded to Free.",
        title="Subscription refunded",
    )
    return billing.invoice_view(out)


@router.post("/admin/promos", status_code=201)
async def create_promo(
    body: PromoCreate,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    promo = await billing.admin_promo_create(db, body.code, body.discount_pct, body.max_uses, body.expires_days)
    if promo.get("error"):
        raise HTTPException(status_code=422, detail=promo["error"])
    return billing.promo_view(promo)


@router.get("/admin/promos")
async def list_promos(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    return [billing.promo_view(p) for p in await billing.admin_promos(db)]


@router.post("/admin/promos/{code}/toggle")
async def toggle_promo(
    code: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    promo = await billing.admin_promo_toggle(db, code)
    if promo.get("error"):
        raise HTTPException(status_code=404, detail=promo["error"])
    return billing.promo_view(promo)


@router.get("/admin/stats")
async def stats(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    return await billing.admin_stats(db)