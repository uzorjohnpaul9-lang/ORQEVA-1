import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db.supabase import get_service_client, SupabaseDB
from backend.db.models import USERS, USER_PREFERENCES
from backend.db.database import seed_admin

async def main():
    ok = await seed_admin()
    print("seed_admin ok:", ok)

    db = SupabaseDB(await get_service_client())
    rows = await db.fetch_all(USERS, columns="id,email,tier,is_active,is_admin,username")
    print("public.users rows:", len(rows))
    for r in rows:
        print("  -", r.get("email"), "| tier:", r.get("tier"), "| is_active:", r.get("is_active"), "| is_admin:", r.get("is_admin"))

    prefs = await db.fetch_all(USER_PREFERENCES, columns="user_id,theme,risk_tolerance")
    print("user_preferences rows:", len(prefs))

asyncio.run(main())