"""Auth flow: register, login, me, lockout, token integrity."""
import httpx

from tests.conftest import register_and_login


async def test_register_login_me(client: httpx.AsyncClient):
    H, email = await register_and_login(client)
    r = await client.get("/api/auth/me", headers=H)
    assert r.status_code == 200
    assert r.json()["email"] == email


async def test_duplicate_register_rejected(client: httpx.AsyncClient):
    payload = {"email": "dup@test.dev", "username": "dupuser", "password": "Testpass123!"}
    r1 = await client.post("/api/auth/register", json=payload)
    r2 = await client.post("/api/auth/register", json=payload)
    assert r2.status_code in (400, 409, 422)


async def test_wrong_password_401(client: httpx.AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "wp@test.dev", "username": "wpuser", "password": "Testpass123!",
    })
    r = await client.post("/api/auth/login", json={"email": "wp@test.dev", "password": "nope"})
    assert r.status_code == 401


async def test_lockout_after_failures(client: httpx.AsyncClient):
    email = "lock@test.dev"
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"email": email, "password": "bad"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"email": email, "password": "bad"})
    assert r.status_code == 429


async def test_tampered_token_rejected(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    forged = H["Authorization"].replace("Bearer ", "")[:-4] + "AAAA"
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code in (401, 403)


async def test_admin_required_for_admin_routes(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)  # plain user
    r = await client.post("/api/engine/scan", headers=H)
    assert r.status_code == 403
