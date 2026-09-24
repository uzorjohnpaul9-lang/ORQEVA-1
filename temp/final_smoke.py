import asyncio
import importlib
import importlib.metadata as m
import sys

sys.path.insert(0, r"C:\Users\Munachi\ai-trading-system")
import backend.main  # ensure config + app import

from backend.config import settings


def mask(v):
    if not v:
        return "<EMPTY>"
    if len(v) <= 16:
        return v
    return v[:14] + "..." + " [" + str(len(v)) + "]"


async def main():
    from backend.db.supabase import get_anon_client, get_service_client
    from supabase import create_async_client
    from supabase.lib.client_options import ClientOptions

    print("=== live client builds (real keys) ===")
    results = []
    for label, fn in (("anon", get_anon_client), ("service", get_service_client)):
        try:
            c = await fn()
            results.append((label, "OK"))
            print("  {:8} -> build OK: {}".format(label, type(c).__name__))
        except Exception as e:
            results.append((label, "FAIL"))
            print("  {:8} -> FAIL: {}: {}".format(label, type(e).__name__, str(e)[:160]))

    print()
    print("=== interpreter + resolution used by uvicorn interpreter ===")
    print("  supabase pkg :", importlib.import_module("supabase").__file__)
    try:
        from supabase.lib.client_options import ClientOptions as CO
        import dataclasses
        print("  ClientOptions fields:", [f.name for f in dataclasses.fields(CO)])
    except Exception as e:
        print("  ClientOptions introspect FAIL:", type(e).__name__, str(e)[:120])

    print()
    print("=== final status ===")
    ok = all(r[1] == "OK" for r in results)
    print("  all clients build :", ok)
    print("  SUPABASE_URL      :", mask(settings.SUPABASE_URL))
    print("  PUBLISHABLE_KEY   :", mask(settings.SUPABASE_PUBLISHABLE_KEY))
    print("  SECRET_KEY        :", mask(settings.SUPABASE_SECRET_KEY))
    print("  JWT_SECRET        :", mask(settings.SUPABASE_JWT_SECRET or ""))
    return 0 if ok else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
