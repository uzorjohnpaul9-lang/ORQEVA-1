import asyncio, httpx

BASE = "https://crysjnakhwveokjrydyw.supabase.co"

async def main():
    key = open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8").read().split("SUPABASE_SECRET_KEY=")[1].splitlines()[0].strip().strip('"')
    h = {"apikey": key, "Authorization": "Bearer " + key}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            BASE + "/rest/v1/rpc/",
            headers=h,
            params={"null": ""},
        )
        # query the schema for public tables
        r = await c.get(
            BASE + "/rest/v1/",
            headers=h,
            params={"Accept": "application/json", "apikey": key},
        )
        print("root rest status", r.status_code)
        print(r.text[:600])

asyncio.run(main())