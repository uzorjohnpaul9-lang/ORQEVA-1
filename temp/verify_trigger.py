import asyncio, sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db.supabase import get_anon_client, get_service_client, SupabaseDB
from backend.db.models import USERS, USER_PREFERENCES

EMAIL = f"trigger_test_{uuid.uuid4().hex[:8]}@test.com"
PASSWORD = "TestPass123!"

async def main():
    anon = await get_anon_client()
    created = None
    try:
        resp = await anon.auth.sign_up({"email": EMAIL, "password": PASSWORD,
                                        "options": {"data": {"username": "tester", "tier": "starter"}}})
        print("signUp result:", type(resp).__name__)
        data = getattr(resp, "data", None)
        if data:
            created = data.get("id") or (getattr(data, "id", None))
            print("  auth user id:", created, "email:", getattr(data, "email", None))
        else:
            print("  sign_up returned", resp)
    except Exception as e:
        print("signUp error:", type(e).__name__, str(e)[:300])
        return

    if created:
        await asyncio.sleep(2)
        svc = await get_service_client()
        db = SupabaseDB(svc)
        u = await db.fetch_one(USERS, {"id": created})
        print("public.users mirror:", u if u else "MISSING")
        p = await db.fetch_one(USER_PREFERENCES, {"user_id": created})
        print("user_preferences mirror:", p if p else "MISSING")
        # cleanup
        try:
            await svc.auth.admin.delete_user(created)
            print("cleanup: deleted test auth user")
        except Exception as e:
            print("cleanup error:", e)
        try:
            await db.delete(USER_PREFERENCES, {"user_id": created})
            await db.delete(USERS, {"id": created})
            print("cleanup: deleted mirror rows")
        except Exception as e:
            print("cleanup mirror error:", e)

asyncio.run(main())