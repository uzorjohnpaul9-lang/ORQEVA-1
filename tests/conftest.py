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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver",
                                 timeout=30.0) as c:
        yield c
    # keep the file for post-mortem; CI can delete it


@pytest.fixture(autouse=True)
def _clean_state():
    from backend.middleware.rate_limiter import rate_limiter
    from backend.middleware import brute_force

    rate_limiter._hits.clear()
    brute_force._failures.clear()

    # CentralRiskEngine persists counters/pnl/positions to
    # data/central_risk_state.json and restores them on construction -
    # stale state from earlier runs would trip the daily-trade and
    # exposure gates mid-session. Start each test from a clean slate.
    try:
        from backend.api import risk as risk_api

        central = risk_api.central
        central.daily_trade_count = {"stock": 0, "forex": 0, "crypto": 0}
        if hasattr(central, "daily_pnl"):
            central.daily_pnl = 0.0
        if hasattr(central, "positions"):
            central.positions = {}
    except Exception:
        pass

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
    import asyncio

    # Supabase occasionally rejects admin.create_user with an empty transient
    # error under rapid signup bursts - retry a few times before failing.
    # Fresh identity each attempt: a create that timed out client-side may
    # still have landed server-side, making the same email "already taken".
    r = None
    for attempt in range(4):
        email = f"t{uuid.uuid4().hex[:10]}@test.dev"
        payload = {
            "email": email, "username": email.split("@")[0], "password": "Testpass123!",
        }
        r = await client.post("/api/auth/register", json=payload)
        if r.status_code in (200, 201):
            break
        if "Sign up failed" not in r.text:
            break
        await asyncio.sleep(2)
    assert r is not None and r.status_code in (200, 201), r.text

    if admin or tier != "free":
        from backend.db.models import USERS
        from backend.db.supabase import SupabaseDB, get_service_client

        svc = await get_service_client()
        await SupabaseDB(svc).update(
            USERS, {"tier": tier, "is_admin": admin}, {"email": email}
        )

    for attempt in range(5):
        r = await client.post("/api/auth/login", json={"email": email, "password": "Testpass123!"})
        if r.status_code == 200:
            break
        await asyncio.sleep(3)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def make_admin(client: httpx.AsyncClient):
    """Promote a fresh user to admin (avoids depending on seeded data)."""
    return await register_and_login(client, admin=True)
