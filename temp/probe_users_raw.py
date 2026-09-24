import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import httpx
from backend.config import settings

async def main():
    url = settings.SUPABASE_URL.rstrip("/") + "/auth/v1/admin/users"
    headers = {
        "apikey": settings.SUPABASE_SECRET_KEY,
        "Authorization": "Bearer " + settings.SUPABASE_SECRET_KEY,
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, headers=headers)
        print("status:", r.status_code)
        body = r.json()
        users = body.get("users", [])
        print("users:", len(users))
        for u in users:
            print("  -", u.get("email"), u.get("id"))

        # also check service client raw via supabase methods
        from backend.db.supabase import get_service_client
        client = await get_service_client()
        resp = await client.auth.admin.list_users()
        print("client list_users raw type:", type(resp).__name__, "len:", len(resp))
        if len(resp):
            print("  first item type:", type(resp[0]).__name__, resp[0])

asyncio.run(main())