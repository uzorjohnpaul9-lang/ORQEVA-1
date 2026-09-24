import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db.supabase import get_service_client, SupabaseDB
from backend.config import settings

async def main():
    client = await get_service_client()
    print("service client OK")
    try:
        resp = await client.auth.admin.list_users()
        data = getattr(resp, "data", None) or []
        print("list_users type:", type(resp).__name__)
        print("total users:", len(data))
        if data:
            print("first keys:", list(data[0].keys()))
            for u in data:
                print("  -", u.get("email"), u.get("id"))
    except Exception as e:
        print("list_users ERR:", type(e).__name__, str(e)[:200])

    db = SupabaseDB(client)
    try:
        row = await db.fetch_one("users", {"id": "x"})
        print("users fetch (no row expected):", row)
    except Exception as e:
        print("users fetch ERR:", type(e).__name__, str(e)[:300])

asyncio.run(main())