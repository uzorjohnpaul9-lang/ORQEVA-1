import asyncio, inspect, sys
from backend.db import supabase as s
from backend.config import settings

async def main():
    print("  config.SUPABASE_URL     =", (settings.SUPABASE_URL or "<EMPTY>"))
    print("  config.PUBLISHABLE present =", bool(settings.SUPABASE_PUBLISHABLE_KEY))
    print("  config.SECRET present    =", bool(settings.SUPABASE_SECRET_KEY))
    print("  facade funcs:", [n for n in dir(s) if n in ("get_service_client","get_anon_client")])
    for anon in (False, True):
        f = s.get_anon_client if anon else s.get_service_client
        try:
            c = await f()
            print("  build anon=%s -> OK, obj=%s" % (anon, type(c).__name__))
        except Exception as e:
            print("  build anon=%s -> FAIL: %s: %s" % (anon, type(e).__name__, e))

asyncio.run(main())
