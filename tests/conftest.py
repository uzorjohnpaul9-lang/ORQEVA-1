"""Test session setup: isolated DB, app client, shared helpers.

DASHBOARD_DATABASE_URL must be set BEFORE backend modules are imported.
"""
import os
import sys
import uuid
from pathlib import Path

TEST_DB = Path(__file__).parent / "test_dashboard.db"
os.environ["DASHBOARD_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport  # noqa: E402


@pytest.fixture(scope="session")
async def client():
    if TEST_DB.exists():
        TEST_DB.unlink()
    from backend.main import app
    from backend.db.database import init_db

    await init_db()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    # keep the file for post-mortem; CI can delete it


@pytest.fixture(autouse=True)
def _clean_state():
    from backend.middleware.rate_limiter import rate_limiter
    from backend.middleware import brute_force

    rate_limiter._hits.clear()
    brute_force._failures.clear()
    yield

    # release the shared engine-level kill switch between tests
    try:
        from backend.api import risk as risk_api

        if getattr(risk_api.central, "kill_switch_active", False):
            risk_api.central.deactivate_kill_switch()
    except Exception:
        pass
    rate_limiter._hits.clear()
    brute_force._failures.clear()


async def register_and_login(client: httpx.AsyncClient, tier: str = "free", admin: bool = False):
    """Create a unique user and return auth headers."""
    email = f"t{uuid.uuid4().hex[:10]}@test.dev"
    r = await client.post("/api/auth/register", json={
        "email": email, "username": email.split("@")[0], "password": "Testpass123!",
    })
    assert r.status_code in (200, 201), r.text

    if admin or tier != "free":
        from sqlalchemy import update
        from backend.db.database import async_session
        from backend.db.models import User

        async with async_session() as db:
            await db.execute(
                update(User).where(User.email == email).values(
                    tier=tier, is_admin=admin,
                )
            )
            await db.commit()

    r = await client.post("/api/auth/login", json={"email": email, "password": "Testpass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def make_admin(client: httpx.AsyncClient):
    """Promote a fresh user to admin (avoids depending on seeded data)."""
    return await register_and_login(client, admin=True)
