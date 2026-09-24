import asyncio, httpx

BASE = "https://crysjnakhwveokjrydyw.supabase.co"

async def main():
    key = open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8").read().split("SUPABASE_SECRET_KEY=")[1].splitlines()[0].strip().strip('"')
    h = {"apikey": key, "Authorization": "Bearer " + key}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(BASE + "/auth/v1/admin/users", headers=h, params={"per_page": 1000, "page": 1})
        r.raise_for_status()
        users = r.json().get("users", [])
        for u in users:
            email = (u.get("email") or "").lower()
            if email == "uzorjohnpaul9@gmail.com":
                meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
                print("id        :", u["id"])
                print("email     :", email)
                print("meta      :", meta)
                print("is_admin  :", meta.get("is_admin"))
                print("ADMIN OK" if meta.get("is_admin") is True else "!! is_admin NOT true")

asyncio.run(main())