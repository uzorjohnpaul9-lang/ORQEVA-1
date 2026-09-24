import asyncio, httpx

BASE = "https://crysjnakhwveokjrydyw.supabase.co"

async def main():
    key = open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8").read().split("SUPABASE_SECRET_KEY=")[1].splitlines()[0].strip().strip('"')
    h = {"apikey": key, "Authorization": "Bearer " + key}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(BASE + "/auth/v1/admin/users", headers=h, params={"per_page": 1000, "page": 1})
        r.raise_for_status()
        payload = r.json()
        users = payload.get("users", [])
        print("total users:", len(users))
        for u in users:
            email = (u.get("email") or "").lower()
            mark = "  <== TARGET" if email == "uzorjohnpaul9@gmail.com" else ""
            print(f"  id={u['id']}  email={email}  confirmed={bool(u.get('email_confirmed_at'))}{mark}")

asyncio.run(main())