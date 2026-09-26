"""DB bootstrap + FastAPI dependency, backed entirely by Supabase.

``get_db`` hands out the async Supabase facade (see backend.db.supabase).
``init_db`` no longer creates schema (that is done once in the Supabase SQL
editor with backend/db/schema.sql); it verifies connectivity and seeds the
admin account through Supabase Auth.
"""
import logging

from backend.db.supabase import (
    SupabaseDB,
    get_anon_client,
    get_db,
    get_service_client,
    now_iso,
)
from backend.db.models import USER_PREFERENCES, USERS, gen_uuid

log = logging.getLogger(__name__)

__all__ = ["get_db", "init_db", "seed_admin"]


async def init_db() -> None:
    """Verify Supabase connectivity and seed the admin account."""
    ok = await seed_admin()
    if not ok:
        log.error("init_db: could not reach Supabase (check SUPABASE_URL / keys)")


async def seed_admin() -> bool:
    """Ensure the env-configured admin exists in Supabase Auth + public.users."""
    import os

    client = await get_service_client()
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or "CHANGE_ME" in email or "example.com" in email or "orqeva.com" in email:
        log.error("seed_admin: set a real ADMIN_EMAIL (and ADMIN_PASSWORD) in .env - skipping placeholder admin")
        return False
    if not password or password == "change_me" or password == "adminpass123":
        log.error("seed_admin: set a strong ADMIN_PASSWORD in .env - skipping placeholder-admin seed")
        return False

    try:
        resp = await client.auth.admin.list_users()
        users = resp if isinstance(resp, list) else (getattr(resp, "data", None) or [])
    except Exception as e:
        log.error("seed_admin: Supabase unreachable: %s", e)
        return False

    auth_id = None
    for u in users:
        email_ = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
        if (email_ or "").lower() == email:
            auth_id = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
            break
    if auth_id is None:
        try:
            created = await client.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"username": email.split("@")[0], "tier": "vip", "is_admin": True},
                }
            )
            auth_id = created.user.id
        except Exception as e:
            log.error("seed_admin: create admin failed: %s", e)
            return False
    else:
        # Keep the seeded password in sync with env, and mirror admin flags into
        # auth user_metadata (the frontend reads is_admin/tier from the JWT).
        try:
            await client.auth.admin.update_user_by_id(
                auth_id,
                {
                    "password": password,
                    "user_metadata": {
                        "username": (email.split("@")[0] or "admin"),
                        "tier": "vip",
                        "is_admin": True,
                    },
                },
            )
        except Exception as e:
            log.error("seed_admin: admin password update failed: %s", e)

    # upsert the public.users mirror row
    row = await SupabaseDB(client).fetch_one(USERS, {"id": auth_id})
    if row is None:
        await SupabaseDB(client).insert(
            USERS,
            {
                "id": auth_id,
                "email": email,
                "username": email.split("@")[0],
                "tier": "vip",
                "is_active": True,
                "is_admin": True,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        await SupabaseDB(client).insert(
            USER_PREFERENCES,
            {
                "id": gen_uuid(),
                "user_id": auth_id,
                "telegram_signals": True,
                "telegram_tp_sl": True,
                "telegram_market_analysis": False,
                "telegram_risk_alerts": True,
                "telegram_system_alerts": True,
                "email_notifications": False,
                "web_notifications": True,
                "default_market": "all",
                "risk_tolerance": "moderate",
                "theme": "dark",
            },
        )
    else:
        await SupabaseDB(client).update(
            USERS,
            {"is_admin": True, "tier": "vip", "is_active": True},
            {"id": auth_id},
        )
    return True


async def readyz() -> dict:
    facade = SupabaseDB(await get_service_client())
    ok = await facade.ping()
    return {"status": "ready", "database": "up" if ok else "down"}