from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.db.supabase import SupabaseDB, get_db, get_service_client
from backend.db.models import USERS

security = HTTPBearer()


async def resolve_user_from_token(token: str) -> str | None:
    """Validate a Supabase access token against the auth provider.

    Returns the user id on success, or None if the token is invalid/expired.
    SSE endpoints can't send Authorization headers, so they share this path.
    """
    try:
        client = await get_service_client()
        resp = await client.auth.get_user(token)
        return resp.user.id
    except Exception:
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