import asyncio, httpx

BASE = "https://crysjnakhwveokjrydyw.supabase.co"

async def main():
    key = open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8").read().split("SUPABASE_SECRET_KEY=")[1].splitlines()[0].strip().strip('"')
    h = {"apikey": key, "Authorization": "Bearer " + key}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(BASE + "/auth/v1/admin/users", headers=h, params={"per_page": 1000})
        print("status", r.status_code)
        data = r.json()
        print("type", type(data).__name__)
        if isinstance(data, list):
            print("len", len(data))
            if data:
                print("first elem type", type(data[0]).__name__)
                print("first elem", str(data[0])[:200])
        else:
            print(str(data)[:400])

asyncio.run(main())