import logging
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.config import settings
from backend.db.supabase import (
    SupabaseDB,
    get_db,
    get_anon_client,
    get_service_client,
    now_iso,
    parse_dt,
)
from backend.db.models import USER_PREFERENCES, USERS, PASSWORD_RESET_TOKENS, gen_uuid
from backend.db.schemas import UserRegister, UserLogin, Token, UserResponse
from backend.auth import get_current_user
from backend.middleware import brute_force

log = logging.getLogger("auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

RESET_TTL_MINUTES = 30


def _absolute_link(path: str) -> str:
    """Join APP_BASE_URL + a root-relative path without doubling slashes.

    A trailing slash on APP_BASE_URL previously produced ``https://host//reset``
    which some mail clients normalise away and others 404 on.
    """
    base = (settings.APP_BASE_URL or "").strip()
    if not base:
        return path
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


class ForgotRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ResetRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserRegister, db: SupabaseDB = Depends(get_db)):
    email = data.email.strip().lower()
    # public.users enforces unique username + email (schema.sql)
    if await db.fetch_one(USERS, {"username": data.username}):
        raise HTTPException(status_code=400, detail="Email or username already taken")
    if await db.fetch_one(USERS, {"email": email}):
        raise HTTPException(status_code=400, detail="Email or username already taken")

    # Create the confirmed Auth user via the service client (no email verification page exists).
    client = await get_service_client()
    try:
        created = await client.auth.admin.create_user(
            {"email": email, "password": data.password, "email_confirm": True}
        )
        auth_id = created.user.id
    except Exception as e:
        detail = str(getattr(e, "message", e) or e)
        if "already been registered" in detail or "already in use" in detail:
            raise HTTPException(status_code=400, detail="Email or username already taken")
        raise HTTPException(status_code=400, detail=f"Sign up failed: {detail}")

    user = {
        "id": auth_id,
        "email": email,
        "username": data.username,
        "tier": "free",
        "is_active": True,
        "is_admin": False,
        "telegram_chat_id": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    # The DB trigger on_auth_user_created mirrors new auth signups into
    # public.users + user_preferences, so only insert when that hasn't fired.
    existing = await db.fetch_one(USERS, {"id": auth_id})
    if existing is None:
        await db.insert(USERS, user)
    if await db.fetch_one(USER_PREFERENCES, {"user_id": auth_id}) is None:
        await db.insert(USER_PREFERENCES, {"id": gen_uuid(), "user_id": auth_id})
    return user


@router.post("/login", response_model=Token)
async def login(data: UserLogin, request: Request, db: SupabaseDB = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    email = data.email.strip().lower()
    locked_for = brute_force.is_locked(email, ip)
    if locked_for:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts - try again in {locked_for}s",
        )

    try:
        anon = await get_anon_client()
        resp = await anon.auth.sign_in_with_password({"email": email, "password": data.password})
        auth_user = resp.user
        access_token = resp.session.access_token
    except Exception as e:
        # AuthApiError carries `status`/`code`; transport failures carry neither.
        # Only treat actual provider credential rejections as 401 - timeouts,
        # 429s and 5xx must not lie to the user or count toward lockout.
        status = getattr(e, "status", None) or getattr(e, "status_code", None)
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None
        transient = status is None and not getattr(e, "code", None)
        if transient or status == 429 or (status is not None and status >= 500):
            raise HTTPException(
                status_code=503,
                detail="Login temporarily unavailable - please retry",
            )
        brute_force.record_failure(email, ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = await db.fetch_one(USERS, {"id": auth_user.id})
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account disabled")

    brute_force.reset(email, ip)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return user


@router.post("/forgot")
async def forgot_password(data: ForgotRequest, db: SupabaseDB = Depends(get_db)):
    """Always returns 200 so the endpoint can't be used to enumerate accounts."""
    import hashlib
    import secrets
    from datetime import datetime, timedelta, timezone

    user = await db.fetch_one(USERS, {"email": data.email.strip().lower()})

    delivered_via_email = False
    if user and user.get("is_active"):
        raw_token = secrets.token_urlsafe(32)
        await db.insert(
            PASSWORD_RESET_TOKENS,
            {
                "id": gen_uuid(),
                "user_id": user["id"],
                "token_hash": hashlib.sha256(raw_token.encode()).hexdigest(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)).isoformat().replace("+00:00", "Z"),
                "used": False,
                "created_at": now_iso(),
            },
        )

        link = _absolute_link(f"/reset?token={raw_token}")
        try:
            from backend.services import email_service

            if email_service.is_configured():
                if "localhost" in settings.APP_BASE_URL or "127.0.0.1" in settings.APP_BASE_URL:
                    log.warning(
                        "SMTP is configured but APP_BASE_URL=%r - reset links will not "
                        "resolve outside this host", settings.APP_BASE_URL,
                    )
                subject, html = email_service.reset_email(user["email"], link)
                delivered_via_email = await email_service.send_email(user["email"], subject, html)
        except Exception as e:
            log.error("reset email delivery failed: %s", e)

        if not delivered_via_email:
            # SMTP unavailable: fall back to channels the locked-out user can still
            # reach. Telegram is the only one that works before sign-in; the in-app
            # notification is kept as an audit trail for when they get back in.
            delivery_channels: list[str] = []
            try:
                from backend.services import notification_service

                msg = f"Password reset requested. Open this link to choose a new password (valid {RESET_TTL_MINUTES} min): {link}"
                await notification_service.create(db, user["id"], "system", "Password reset", msg)
                delivery_channels.append("in_app")
                if user.get("telegram_chat_id"):
                    from backend.services.telegram_service import send_message

                    tier_cfg = {"free": "FREE", "premium": "PREMIUM", "vip": "VIP"}
                    token_env = f"TELEGRAM_BOT_TOKEN_{tier_cfg.get(user.get('tier'), 'FREE')}"
                    import os

                    bot_tok = os.getenv(token_env, "")
                    if bot_tok:
                        await send_message(bot_tok, user["telegram_chat_id"], msg)
                        delivery_channels.append("telegram")
            except Exception as e:
                log.error("reset fallback delivery failed: %s", e)

            if "telegram" not in delivery_channels:
                # No channel the user can read while signed out. Log for operators so
                # they can issue a temp password (admin /users/{id}/reset-password).
                log.warning(
                    "password reset for %s delivered via %s only; user may be locked out",
                    user["email"], delivery_channels or ["none"],
                )

    return {"status": "ok",
            "message": "If that account exists, a reset link has been sent."}


@router.post("/reset")
async def reset_password(data: ResetRequest, db: SupabaseDB = Depends(get_db)):
    import hashlib
    from datetime import datetime, timezone

    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    rec = await db.fetch_one(PASSWORD_RESET_TOKENS, {"token_hash": token_hash, "used": False})
    # Compare parsed datetimes, not ISO strings: PostgREST returns "...+00:00"
    # while we store "...Z", and '+' sorts before 'Z' lexicographically - a raw
    # string compare would flag live tokens as expired.
    expires = parse_dt(rec.get("expires_at")) if rec else None
    if not rec or expires is None or expires <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    user = await db.fetch_one(USERS, {"id": rec["user_id"]})
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=400, detail="Account unavailable")

    # Set the new password in Supabase Auth via the service client.
    try:
        client = await get_service_client()
        await client.auth.admin.update_user_by_id(user["id"], {"password": data.new_password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Password update failed: {getattr(e, 'message', e)}")

    await db.update(PASSWORD_RESET_TOKENS, {"used": True}, {"token_hash": token_hash})
    # invalidate any other live tokens for this account (single-use semantics)
    await db.update(PASSWORD_RESET_TOKENS, {"used": True}, {"user_id": user["id"], "used": False})

    # clear any brute-force counters for this account (all source IPs)
    brute_force.reset_all(user["email"])
    return {"status": "ok", "message": "Password updated - you can sign in now."}