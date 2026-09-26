import asyncio, httpx, logging, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def _load_env():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

_load_env()
from backend.main import app

async def main():
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=8011, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(4.0)
    async with httpx.AsyncClient(timeout=25) as c:
        # login as the seeded admin via /api/auth/login (backend endpoint)
        email = os.getenv("ADMIN_EMAIL", "") or "CHANGE_ME"
        password = os.getenv("ADMIN_PASSWORD", "")
        r = await c.post("http://127.0.0.1:8011/api/auth/login", json={"email": email, "password": password})
        print("LOGIN:", r.status_code, r.text[:200])
        if r.status_code != 200:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=10)
            return
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        for label, method, url in [
            ("ADMIN USERS", "GET", "/api/admin/users?limit=10"),
            ("ADMIN SYSTEM", "GET", "/api/admin/system"),
            ("ADMIN AUDIT", "GET", "/api/admin/audit"),
            ("ADMIN SUBS", "GET", "/api/admin/subscriptions"),
            ("ADMIN SIGNALS", "GET", "/api/admin/signals"),
        ]:
            try:
                rr = await c.request(method, "http://127.0.0.1:8011" + url, headers=h)
                print(f"{label}: {rr.status_code} {rr.text[:300]}")
            except Exception as e:
                print(f"{label}: ERROR {e}")

        # non-admin should be blocked: register throwaway user then hit /api/admin
        rr = await c.post("http://127.0.0.1:8011/api/auth/register",
                          json={"email": "nope_admin_test@example.com", "username": "nopeadmintest", "password": "somepass123"})
        print("REGISTER THROWAWAY:", rr.status_code)
        rr = await c.post("http://127.0.0.1:8011/api/auth/login",
                          json={"email": "nope_admin_test@example.com", "password": "somepass123"})
        if rr.status_code == 200:
            t2 = rr.json()["access_token"]
            h2 = {"Authorization": f"Bearer {t2}"}
            rr = await c.get("http://127.0.0.1:8011/api/admin/users", headers=h2)
            print("NON-ADMIN /api/admin/users:", rr.status_code, rr.text[:100])
    server.should_exit = True
    await asyncio.wait_for(task, timeout=10)

asyncio.run(main())