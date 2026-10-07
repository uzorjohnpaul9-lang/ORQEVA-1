"""Hardening sprint: admin seed, idempotency, password reset flow."""
import hashlib
import os

import pytest

from tests.conftest import register_and_login


async def test_env_admin_seeded_and_rotated(client, monkeypatch):
    """ADMIN_PASSWORD env must (re)apply on every boot via seed_admin."""
    import uuid as _uuid

    from backend.db.database import seed_admin
    from backend.db.models import USER_PREFERENCES, USERS
    from backend.db.supabase import SupabaseDB, get_anon_client, get_service_client

    email = f"seedadmin{_uuid.uuid4().hex[:8]}@test.dev"
    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", "RotatedPass123!")
    monkeypatch.setenv("ADMIN_SEED_FORCE", "1")

    svc = await get_service_client()
    db = SupabaseDB(svc)
    try:
        assert await seed_admin() is True
        row = await db.fetch_one(USERS, {"email": email})
        assert row and row["is_admin"] and row["tier"] == "vip"

        anon = await get_anon_client()
        resp = await anon.auth.sign_in_with_password(
            {"email": email, "password": "RotatedPass123!"}
        )
        assert resp.user

        # rotate the env password -> force seed applies it immediately
        monkeypatch.setenv("ADMIN_PASSWORD", "SecondRot99!")
        assert await seed_admin() is True
        resp = await anon.auth.sign_in_with_password(
            {"email": email, "password": "SecondRot99!"}
        )
        assert resp.user
    finally:
        row = await db.fetch_one(USERS, {"email": email}, columns="id")
        if row:
            await db.delete(USER_PREFERENCES, {"user_id": row["id"]})
            await db.delete(USERS, {"id": row["id"]})
        try:
            users = await svc.auth.admin.list_users()
            users = users if isinstance(users, list) else (getattr(users, "data", None) or [])
            for u in users:
                u_email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
                if (u_email or "").lower() == email:
                    await svc.auth.admin.delete_user(getattr(u, "id", None) or u.get("id"))
        except Exception:
            pass


async def test_order_idempotency_replay(client):
    """Same idempotency key returns the original response; no duplicate trade."""
    H, _ = await register_and_login(client)
    body = {"symbol": "AAPL", "market": "stock", "side": "buy",
            "quantity": 1, "entry_price": 100.0, "idempotency_key": "key-abc-1"}

    r1 = await client.post("/api/trading/orders", json=body, headers=H)
    assert r1.status_code == 200, r1.text
    r2 = await client.post("/api/trading/orders", json=body, headers=H)
    assert r2.status_code == 200
    assert r2.json()["trade_id"] == r1.json()["trade_id"]

    rh = await client.get("/api/trading/history?outcome=open", headers=H)
    opens = [t for t in rh.json()["trades"]]
    assert sum(1 for t in opens if t["id"] == r1.json()["trade_id"]) == 1


async def test_order_idempotency_different_key_new_trade(client):
    H, _ = await register_and_login(client)
    base = {"symbol": "MSFT", "market": "stock", "side": "buy",
            "quantity": 1, "entry_price": 300.0}
    r1 = await client.post("/api/trading/orders",
                           json={**base, "idempotency_key": "k1"}, headers=H)
    r2 = await client.post("/api/trading/orders",
                           json={**base, "idempotency_key": "k2"}, headers=H)
    assert r1.json()["trade_id"] != r2.json()["trade_id"]


async def test_forgot_password_never_enumerates(client):
    r_real = await client.post("/api/auth/forgot", json={"email": "admin@demo.com"})
    r_fake = await client.post("/api/auth/forgot", json={"email": "nobody@nowhere.dev"})
    assert r_real.status_code == r_fake.status_code == 200
    assert r_real.json() == r_fake.json()


async def test_full_password_reset_flow(client):
    """forgot -> token delivered via notification fallback -> reset -> login with new pw."""
    H, email = await register_and_login(client)

    r = await client.post("/api/auth/forgot", json={"email": email})
    assert r.status_code == 200

    # SMTP is unconfigured in tests: the link lands in the in-app notification center
    notes = (await client.get("/api/notifications", headers=H)).json()["notifications"]
    reset_notes = [n for n in notes if "reset" in (n.get("title") or "").lower()]
    assert reset_notes, f"expected fallback notification, got {[n.get('title') for n in notes]}"
    import re
    m = re.search(r"token=([\w\-]+)", reset_notes[-1]["message"])
    assert m, "notification must contain the reset link"
    raw_token = m.group(1)

    rr = await client.post("/api/auth/reset", json={
        "token": raw_token, "new_password": "NewPass456!"})
    assert rr.status_code == 200, rr.text

    # old password dead, new one works
    bad = await client.post("/api/auth/login", json={"email": email, "password": "Testpass123!"})
    assert bad.status_code == 401
    good = await client.post("/api/auth/login", json={"email": email, "password": "NewPass456!"})
    assert good.status_code == 200

    # token is single-use
    again = await client.post("/api/auth/reset", json={
        "token": raw_token, "new_password": "Reused789!"})
    assert again.status_code == 400


async def test_reset_rejects_bad_token(client):
    fake = hashlib.sha256(b"not-a-real-token").hexdigest()
    r = await client.post("/api/auth/reset", json={
        "token": "x" * 40, "new_password": "Whatever123!"})
    assert r.status_code == 400
