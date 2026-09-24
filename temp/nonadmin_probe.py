import asyncio, httpx, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
from backend.main import app

async def main():
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=8013, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(4.0)
    email = f"nf{time.time_ns()%100000}@example.com"
    async with httpx.AsyncClient(timeout=25) as c:
        rr = await c.post("http://127.0.0.1:8013/api/auth/register",
                          json={"email": email, "username": "nftest02", "password": "somepass123"})
        print("REGISTER:", rr.status_code)
        uid = rr.json()["id"]
        # confirm email via service client
        from backend.db.supabase import get_service_client
        sc = await get_service_client()
        await sc.auth.admin.update_user_by_id(uid, {"email_confirm": True})
        rr = await c.post("http://127.0.0.1:8013/api/auth/login",
                          json={"email": email, "password": "somepass123"})
        print("LOGIN THROWAWAY:", rr.status_code)
        if rr.status_code == 200:
            t2 = rr.json()["access_token"]
            h2 = {"Authorization": f"Bearer {t2}"}
            rr = await c.get("http://127.0.0.1:8013/api/admin/users", headers=h2)
            print("NON-ADMIN /api/admin/users:", rr.status_code, rr.text[:120])
        # also test a PATCH self-protection? skip; cleanup below
    server.should_exit = True
    await asyncio.wait_for(task, timeout=10)

asyncio.run(main())