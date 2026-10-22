import asyncio

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.db.supabase import SupabaseDB, get_db, get_service_client
from backend.db.models import USERS

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def _auth_error_status(exc: Exception) -> int | None:
    """HTTP status carried by an auth-provider error, if any."""
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


async def resolve_user_from_token(token: str) -> str | None:
    """Validate a Supabase access token against the auth provider.

    Returns the user id on success, or None if the token is invalid/expired.
    SSE endpoints can't send Authorization headers, so they share this path.
    Transient provider hiccups (throttling/network/5xx) are retried with
    backoff: a real credential rejection answers immediately, but a transport
    failure must not surface as a spurious 401 mid-session.
    """
    client = await get_service_client()
    for attempt in range(3):
        try:
            resp = await client.auth.get_user(token)
            return resp.user.id
        except Exception as e:
            status = _auth_error_status(e)
            if status is not None and status < 500 and status != 429:
                # 400/401/403 - the provider rejected the token itself.
                return None
            if attempt == 2:
                return None
            await asyncio.sleep(0.5 * (2 ** attempt))
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: SupabaseDB = Depends(get_db),
) -> dict:
    """Validate a Supabase access token and return the matching public.users row."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = await resolve_user_from_token(credentials.credentials)
    if not user_id:
        raise credentials_exception

    user = await db.fetch_one(USERS, {"id": user_id})
    if not user or not user.get("is_active"):
        raise credentials_exception
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: SupabaseDB = Depends(get_db),
) -> dict | None:
    """Return the caller when a valid token is supplied, else None.

    For endpoints that are public but enrich the response when signed in
    (e.g. the support channel, reachable from the login page).
    """
    if credentials is None:
        return None
    user_id = await resolve_user_from_token(credentials.credentials)
    if not user_id:
        return None
    user = await db.fetch_one(USERS, {"id": user_id})
    if not user or not user.get("is_active"):
        return None
    return user