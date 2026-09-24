import asyncio
import dataclasses
import importlib
import importlib.metadata as meta
import sys

from backend.config import settings


def mask(v):
    return v if not v else (v[:14] + "..." + "[" + str(len(v)) + "]") if len(v) > 14 else v


# 1) what does THIS interpreter resolve for the imports the failure path uses?
def resolve(mod):
    try:
        m = importlib.import_module(mod)
        return getattr(m, "__file__", "<builtin>")
    except Exception as e:
        return "ERR:" + type(e).__name__ + ": " + str(e)[:80]


print("=== import resolution in the failing interpreter ===")
for mod in ("supabase", "supabase_auth", "storage3", "postgrest", "realtime", "supabase_functions"):
    print("  {:20} -> {}\n".format(mod, resolve(mod)))

# 2) the EXACT ClientOptions that supabase/_async/client.py binds
from supabase._async.client import AsyncClient  # noqa: E402
from supabase._async.client import ClientOptions as RuntimeClientOptions  # noqa: E402

fields = [f.name for f in dataclasses.fields(RuntimeClientOptions)]
print("=== ClientOptions as bound in supabase/_async/client.py ===")
print("  fields:", fields)
print("  has storage:", "storage" in fields)

# 3) build both clients for real (live keys)
async def main():
    from backend.db.supabase import get_anon_client, get_service_client

    anon = await get_anon_client()
    print("\n=== anon client build: OK ->", type(anon).__name__)
    svc = await get_service_client()
    print("=== service client build: OK ->", type(svc).__name__)


print("\n=== supabase versions ===")
for p in ("supabase", "supabase-auth", "storage3", "postgrest", "realtime"):
    try:
        print("  {:18} = {}".format(p, meta.version(p)))
    except Exception as e:
        print("  {:18} = <none> ({})".format(p, e))

if __name__ == "__main__":
    asyncio.run(main())
