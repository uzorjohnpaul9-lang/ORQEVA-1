"""Phase K: broker / prop-firm affiliate partners + click & conversion tracking.

Partners are admin-managed rows; clicks are recorded when a signed-in user
follows a partner link, and conversions are credited last-touch to the most
recent partner link that user opened at the moment a payment activates.
"""
import logging
import re

from backend.db.models import (
    AFFILIATE_CLICKS,
    AFFILIATE_CONVERSIONS,
    AFFILIATE_PARTNERS,
    gen_uuid,
)
from backend.db.supabase import SupabaseDB, now_iso

logger = logging.getLogger(__name__)

CATEGORIES = ("broker", "prop_firm", "partner")


def _safe_url(url: str | None) -> str:
    """Only http(s) links are stored/served, so a partner entry cannot inject a
    javascript:/data: URL into the dashboard."""
    value = (url or "").strip()
    if not re.match(r"^https?://", value, re.I):
        return ""
    return value[:500]


def partner_view(row: dict, *, include_stats: bool = True) -> dict:
    out = {
        "id": row.get("id"),
        "name": row.get("name"),
        "url": row.get("url"),
        "category": row.get("category") or "broker",
        "active": bool(row.get("active", True)),
        "created_at": row.get("created_at"),
    }
    if include_stats:
        clicks = int(row.get("click_count") or 0)
        conversions = int(row.get("conversion_count") or 0)
        out.update({
            "click_count": clicks,
            "conversion_count": conversions,
            "revenue_usd": round(float(row.get("revenue_usd") or 0), 2),
            "conversion_rate": round(conversions / clicks * 100, 1) if clicks else 0.0,
        })
    return out


async def list_partners(db: SupabaseDB, *, active_only: bool = True,
                        category: str | None = None) -> list[dict]:
    where: dict = {}
    if active_only:
        where["active"] = True
    if category:
        where["category"] = category
    rows = await db.fetch_all(AFFILIATE_PARTNERS, where=where or None, order="name.asc")
    return [partner_view(r, include_stats=False) for r in rows]


async def admin_list_partners(db: SupabaseDB) -> list[dict]:
    rows = await db.fetch_all(AFFILIATE_PARTNERS, order="created_at.desc")
    return [partner_view(r) for r in rows]


async def create_partner(db: SupabaseDB, *, name: str, url: str,
                         category: str = "broker") -> dict:
    clean = _safe_url(url)
    if not (name or "").strip() or not clean:
        return {"error": "invalid_partner"}
    if category not in CATEGORIES:
        category = "broker"
    row = {
        "id": gen_uuid(),
        "name": name.strip()[:120],
        "url": clean,
        "category": category,
        "click_count": 0,
        "conversion_count": 0,
        "revenue_usd": 0,
        "active": True,
        "created_at": now_iso(),
    }
    return partner_view(await db.insert(AFFILIATE_PARTNERS, row))


async def set_partner_active(db: SupabaseDB, partner_id: str, active: bool) -> dict | None:
    rows = await db.update(AFFILIATE_PARTNERS, {"active": active}, where={"id": partner_id})
    return partner_view(rows[0]) if rows else None


async def record_click(db: SupabaseDB, partner_id: str, user_id: str | None) -> dict | None:
    """Log a click and bump the counter. Unknown/inactive partners return None."""
    partner = await db.fetch_one(AFFILIATE_PARTNERS, {"id": partner_id})
    if not partner or not partner.get("active", True):
        return None
    await db.insert(AFFILIATE_CLICKS, {
        "id": gen_uuid(),
        "partner_id": partner_id,
        "user_id": user_id,
        "created_at": now_iso(),
    })
    await db.update(
        AFFILIATE_PARTNERS,
        {"click_count": int(partner.get("click_count") or 0) + 1},
        where={"id": partner_id},
    )
    return partner_view(partner, include_stats=False)


async def record_conversion(db: SupabaseDB, *, user_id: str, invoice: dict) -> dict | None:
    """Last-touch attribution: credit the most recent partner link the user opened."""
    clicks = await db.fetch_all(
        AFFILIATE_CLICKS, where={"user_id": user_id}, order="created_at.desc", limit=1
    )
    if not clicks:
        return None
    partner_id = clicks[0].get("partner_id")
    partner = await db.fetch_one(AFFILIATE_PARTNERS, {"id": partner_id}) if partner_id else None
    if not partner:
        return None

    amount = round(float(invoice.get("amount_usd") or 0), 2)
    await db.insert(AFFILIATE_CONVERSIONS, {
        "id": gen_uuid(),
        "partner_id": partner_id,
        "user_id": user_id,
        "invoice_id": invoice.get("id"),
        "amount_usd": amount,
        "created_at": now_iso(),
    })
    await db.update(
        AFFILIATE_PARTNERS,
        {
            "conversion_count": int(partner.get("conversion_count") or 0) + 1,
            "revenue_usd": round(float(partner.get("revenue_usd") or 0) + amount, 2),
        },
        where={"id": partner_id},
    )
    return {"partner_id": partner_id, "amount_usd": amount}


async def summary(db: SupabaseDB) -> dict:
    rows = await db.fetch_all(AFFILIATE_PARTNERS)
    clicks = sum(int(r.get("click_count") or 0) for r in rows)
    conversions = sum(int(r.get("conversion_count") or 0) for r in rows)
    revenue = round(sum(float(r.get("revenue_usd") or 0) for r in rows), 2)
    return {
        "partners": len(rows),
        "clicks": clicks,
        "conversions": conversions,
        "revenue_usd": revenue,
        "conversion_rate": round(conversions / clicks * 100, 1) if clicks else 0.0,
    }
