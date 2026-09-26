import asyncio, json, os, uuid
import httpx

BASE = "https://crysjnakhwveokjrydyw.supabase.co"

def secret_key():
    with open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("SUPABASE_SECRET_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no SUPABASE_SECRET_KEY in .env")

def admin_password():
    with open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no ADMIN_PASSWORD in .env")

def admin_email():
    with open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("ADMIN_EMAIL="):
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no ADMIN_EMAIL in .env")

async def main():
    key = secret_key()
    email = admin_email()
    password = admin_password()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as cli:
        # 1) find existing admin user
        r = await cli.get(f"{BASE}/auth/v1/admin/users", headers=headers, params={"per_page": 1000, "page": 1})
        r.raise_for_status()
        payload = r.json()
        users = payload.get("users", []) if isinstance(payload, dict) else payload
        existing = next((u for u in users if (u.get("email") or "").lower() == email), None)

        if existing is None:
            created = await cli.post(
                f"{BASE}/auth/v1/admin/users",
                headers=headers,
                json={"email": email, "password": password, "email_confirm": True,
                      "user_metadata": {"username": email.split("@")[0], "is_admin": True, "tier": "vip"}},
            )
            created.raise_for_status()
            uid = created.json()["id"]
            print("ADMIN_CREATED", uid, email, "created_at=", created.json().get("created_at"))
        else:
            uid = existing["id"]
            upd = await cli.put(
                f"{BASE}/auth/v1/admin/users/{uid}",
                headers=headers,
                json={"email": email, "password": password, "email_confirm": True,
                      "user_metadata": {"username": email.split("@")[0], "is_admin": True, "tier": "vip"}},
            )
            upd.raise_for_status()
            print("ADMIN_UPDATED", uid, email, "created_at=", existing.get("created_at"))

        # 2) upsert public.users mirror row
        pr = await cli.post(
            f"{BASE}/rest/v1/users",
            headers=headers,
            json={"id": uid, "email": email, "username": email.split("@")[0],
                  "tier": "vip", "is_active": True, "is_admin": True},
            params={"on_conflict": "id"},
        )
        if pr.status_code not in (200, 201, 204):
            # try upsert via on_conflict with patch
            pr = await cli.patch(
                f"{BASE}/rest/v1/users?id=eq.{uid}", headers=headers,
                json={"email": email, "username": email.split("@")[0],
                      "tier": "vip", "is_active": True, "is_admin": True},
            )
            if pr.status_code not in (200, 204):
                print("USERS_UPSERT_WARNING", pr.status_code, pr.text[:200])
            else:
                print("USERS_ROW_OK (patched)")
        else:
            # ensure the row exists even if nobody had it; if conflict happened we patched? just report
            print("USERS_ROW_OK", pr.status_code)

        # 3) ensure preferences row exists
        pr = await cli.get(f"{BASE}/rest/v1/user_preferences?user_id=eq.{uid}", headers=headers)
        pr.raise_for_status()
        if not pr.json():
            nid = str(uuid.uuid4())
            x = await cli.post(
                f"{BASE}/rest/v1/user_preferences", headers=headers,
                json={"id": nid, "user_id": uid, "telegram_signals": True, "telegram_tp_sl": True,
                      "telegram_market_analysis": False, "telegram_risk_alerts": True,
                      "telegram_system_alerts": True, "email_notifications": False,
                      "web_notifications": True, "default_market": "all",
                      "risk_tolerance": "moderate", "theme": "dark"},
            )
            print("PREFERENCES_ROW_OK", x.status_code)
        else:
            print("PREFERENCES_EXIST_ALREADY")

asyncio.run(main())