import asyncio
import dataclasses
import sys

from backend.config import settings

sys.path.insert(0, r"C:\Users\Munachi\ai-trading-system")

print("=== config resolves (masked) ===")
def mask(v):
    if not v: return "<EMPTY>"
    if len(v) <= 16: return v
    return v[:14] + "..." + "[" + str(len(v)) + "]"

print("  URL =", mask(settings.SUPABASE_URL))
print("  PUB =", mask(settings.SUPABASE_PUBLISHABLE_KEY))
print("  SEC =", mask(settings.SUPABASE_SECRET_KEY))
print("  JWT =", mask(settings.SUPABASE_JWT_SECRET))
print()

from supabase.lib.client_options import ClientOptions
print("=== ClientOptions fields (this interpreter) ===")
fields = dataclasses.fields(ClientOptions)
print([f.name for f in fields])
print("  has storage:", "storage" in [f.name for f in fields])
print()

from backend.db.supabase import get_anon_client, get_service_client

async def main():
    for name, fn in (("service", get_service_client), ("anon", get_anon_client)):
        try:
            c = await fn()
            print("  build {} client -> OK ({})".format(name, type(c).__name__))
        except Exception as e:
            print("  build {} client -> FAIL: {}: {}".format(name, type(e).__name__, str(e)[:160]))

asyncio.run(main())
