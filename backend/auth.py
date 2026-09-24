from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.db.supabase import SupabaseDB, get_db, get_service_client
from backend.db.models import USERS

security = HTTPBearer()


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
    try:
        client = await get_service_client()
        resp = await client.auth.get_user(credentials.credentials)
        auth_user = resp.user
        user_id = auth_user.id
    except Exception:
        raise credentials_exception

    user = await db.fetch_one(USERS, {"id": user_id}) if user_id else None
    if not user or not user.get("is_active"):
        raise credentials_exception
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user