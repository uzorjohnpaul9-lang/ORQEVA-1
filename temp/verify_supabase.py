import asyncio
import sys

from backend.config import settings

def mask(v):
    if not v:
        return "<EMPTY>"
    if len(v) <= 20:
        return v
    return v[:16] + "..." + "[" + str(len(v)) + "]"

print("config resolves:")
print("  SUPABASE_URL             =", mask(settings.SUPABASE_URL))
print("  SUPABASE_PUBLISHABLE_KEY =", mask(settings.SUPABASE_PUBLISHABLE_KEY))
print("  SUPABASE_SECRET_KEY      =", mask(settings.SUPABASE_SECRET_KEY))
print("  SUPABASE_JWT_SECRET      =", mask(settings.SUPABASE_JWT_SECRET))
print()

from backend.db.supabase import get_service_client, get_anon_client


async def main():
    sc = await get_service_client()
    ac = await get_anon_client()
    print("FACADE OK - get_service_client ->", type(sc).__name__)
    print("FACADE OK - get_anon_client    ->", type(ac).__name__)
    try:
        await sc.ping()
        print("SERVICE PING OK")
    except Exception as e:
        print("service ping failed (may need schema):", type(e).__name__, e)


asyncio.run(main())
