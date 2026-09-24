import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db.supabase import get_service_client, SupabaseDB
from backend.db.models import USERS, USER_PREFERENCES

TARGET = "b81c6663-6149-4126-ac56-246eac6a657d"

async def main():
    svc = await get_service_client()
    db = SupabaseDB(svc)
    u = await db.fetch_one(USERS, {"id": TARGET})
    print("public.users mirror:", u if u else "MISSING")
    p = await db.fetch_one(USER_PREFERENCES, {"user_id": TARGET})
    print("user_preferences mirror:", p if p else "MISSING")
    try:
        await svc.auth.admin.delete_user(TARGET)
        print("cleanup: deleted test auth user")
    except Exception as e:
        print("cleanup auth error:", e)
    try:
        await db.delete(USER_PREFERENCES, {"user_id": TARGET})
        await db.delete(USERS, {"id": TARGET})
        print("cleanup: deleted mirror rows")
    except Exception as e:
        print("cleanup mirror error:", e)

asyncio.run(main())