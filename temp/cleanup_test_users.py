import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from backend.db.supabase import SupabaseDB, get_service_client
from backend.db.models import USERS

async def main():
    client = await get_service_client()
    db = SupabaseDB(client)
    # remove stale test users from public.users (auth side may or may not exist)
    stale = await db.fetch_all(USERS)
    for u in stale:
        email = (u.get("email") or "").lower()
        if email in ("nope_admin_test@example.com", "shapecheck@example.com"):
            await db.delete(USERS, {"id": u["id"]})
            try:
                await client.auth.admin.delete_user(u["id"])
            except Exception:
                pass
            print("cleaned", email, u["id"])
    print("remaining users:", [(u.get("email"), u.get("is_admin")) for u in await db.fetch_all(USERS)])

asyncio.run(main())