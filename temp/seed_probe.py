import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from backend.db.database import seed_admin
from backend.db.supabase import get_anon_client

async def main():
    ok = await seed_admin()
    print("seed_admin:", ok)
    email = os.getenv("ADMIN_EMAIL", "admin@demo.com")
    password = os.getenv("ADMIN_PASSWORD", "adminpass123")
    client = await get_anon_client()
    try:
        r = await client.auth.sign_in_with_password({"email": email, "password": password})
        print("SIGNIN OK:", r.data["user"]["email"], "is_admin=", r.data["user"].get("user_metadata", {}).get("is_admin"))
    except Exception as e:
        print("SIGNIN FAIL:", getattr(e, "message", e))

asyncio.run(main())