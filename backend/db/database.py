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
    """Verify Supabase connectivity and seed the admin account.

    Never raises: a misconfigured or unreachable Supabase must leave the app
    running (``/readyz`` reports ``database: down``) instead of crash-looping.
    """
    try:
        ok = await seed_admin()
    except Exception as e:
        log.error("init_db: Supabase init failed: %s", e)
        return
    if not ok:
        log.error("init_db: could not reach Supabase (check SUPABASE_URL / keys)")


async def _unique_username(
    facade: SupabaseDB, email: str, exclude_id: str | None = None
) -> str:
    """Pick a public.users.username that is not already taken.

    ``seed_admin`` sends this to Supabase Auth as ``user_metadata.username``,
    which the ``handle_new_user`` trigger copies verbatim into
    ``public.users.username``. That column is unique, so a collision here aborts
    (and rolls back) the entire auth-user insert with a generic
    "Database error creating new user". Starting from the email local part, we
    fall back to ``local_domain`` and then ``local_domain_N`` until one is free.

    ``exclude_id`` lets an existing account keep its own username instead of
    treating it as a collision with itself.
    """
    local, _, domain = email.partition("@")
    local = local or "user"
    domain_label = domain.split(".")[0] or "user"

    async def is_free(candidate: str) -> bool:
        row = await facade.fetch_one(USERS, {"username": candidate[:100]}, columns="id")
        return row is None or (exclude_id is not None and row.get("id") == exclude_id)

    for candidate in (local, f"{local}_{domain_label}"):
        if await is_free(candidate):
            return candidate[:100]

    suffix = 1
    while True:
        candidate = f"{local}_{domain_label}_{suffix}"
        if await is_free(candidate):
            return candidate[:100]
        suffix += 1


async def seed_admin() -> bool:
    """Ensure the env-configured admin exists in Supabase Auth + public.users."""
    import asyncio
    import os

    import httpx

    try:
        client = await get_service_client()
    except Exception as e:
        log.error("seed_admin: could not create Supabase client: %s", e)
        return False
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or "CHANGE_ME" in email or "example.com" in email or "orqeva.com" in email:
        log.error("seed_admin: set a real ADMIN_EMAIL (and ADMIN_PASSWORD) in .env - skipping placeholder admin")
        return False
    if not password or password == "change_me" or password == "adminpass123":
        log.error("seed_admin: set a strong ADMIN_PASSWORD in .env - skipping placeholder-admin seed")
        return False

    facade = SupabaseDB(client)

    users = None
    last_err = None
    for attempt in range(3):
        try:
            resp = await client.auth.admin.list_users()
            users = resp if isinstance(resp, list) else (getattr(resp, "data", None) or [])
            break
        except Exception as e:
            last_err = e
            # Transport failures are worth retrying: a DNS blip at boot must not
            # leave the admin unseeded. Auth/permission errors are not.
            if not isinstance(e, (httpx.ConnectError, httpx.TransportError)) or attempt == 2:
                break
            await asyncio.sleep(0.5 * (attempt + 1))
    if users is None:
        log.error("seed_admin: Supabase unreachable: %s", last_err)
        return False

    auth_id = None
    for u in users:
        email_ = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
        if (email_ or "").lower() == email:
            auth_id = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
            break

    # Resolve up-front: the handle_new_user trigger mirrors this value into the
    # unique public.users.username column, so a taken name would roll back the
    # auth-user insert entirely.
    username = await _unique_username(facade, email, exclude_id=auth_id)

    if auth_id is None:
        import asyncio

        last_err = None
        for attempt in range(3):
            try:
                created = await client.auth.admin.create_user(
                    {
                        "email": email,
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": {"username": username, "tier": "vip", "is_admin": True},
                    }
                )
                auth_id = created.user.id
                break
            except Exception as e:
                # Supabase occasionally rejects admin.create_user with a
                # transient empty error under load; retry before giving up,
                # otherwise the deployment boots with no admin at all.
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(2)
        if auth_id is None:
            # A timed-out create may have actually landed - the retry then
            # fails with "already registered". Pick the id up instead of
            # booting with a half-seeded admin.
            try:
                resp = await client.auth.admin.list_users()
                users = resp if isinstance(resp, list) else (getattr(resp, "data", None) or [])
                for u in users:
                    email_ = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
                    if (email_ or "").lower() == email:
                        auth_id = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
                        break
            except Exception:
                pass
        if auth_id is None:
            log.error("seed_admin: create admin failed: %s", last_err)
            return False
    else:
        # Admin exists already. Force-overwriting the password on every boot
        # silently reverted any password the admin changed in the UI, so the
        # existing account is left untouched unless explicitly requested.
        if os.getenv("ADMIN_SEED_FORCE", "").strip().lower() in ("1", "true", "yes"):
            try:
                await client.auth.admin.update_user_by_id(
                    auth_id,
                    {
                        "password": password,
                        "user_metadata": {
                            "username": username,
                            "tier": "vip",
                            "is_admin": True,
                        },
                    },
                )
                log.warning("seed_admin: admin password force-reset from ADMIN_PASSWORD")
            except Exception as e:
                log.error("seed_admin: admin password update failed: %s", e)
        else:
            # Keep the admin flags correct without touching the credential.
            try:
                await client.auth.admin.update_user_by_id(
                    auth_id,
                    {
                        "user_metadata": {
                            "username": username,
                            "tier": "vip",
                            "is_admin": True,
                        },
                    },
                )
            except Exception as e:
                log.error("seed_admin: admin metadata sync failed: %s", e)

    # upsert the public.users mirror row
    row = await facade.fetch_one(USERS, {"id": auth_id})
    if row is None:
        await facade.insert(
            USERS,
            {
                "id": auth_id,
                "email": email,
                "username": username,
                "tier": "vip",
                "is_active": True,
                "is_admin": True,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        await facade.insert(
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
        await facade.update(
            USERS,
            {"is_admin": True, "tier": "vip", "is_active": True},
            {"id": auth_id},
        )
    return True


async def readyz() -> dict:
    facade = SupabaseDB(await get_service_client())
    ok = await facade.ping()
    return {"status": "ready", "database": "up" if ok else "down"}