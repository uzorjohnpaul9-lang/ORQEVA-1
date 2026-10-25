"""Test session setup: isolated DB, app client, shared helpers.

DASHBOARD_DATABASE_URL must be set BEFORE backend modules are imported.
"""
import asyncio
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


class RetryOn503(httpx.AsyncBaseTransport):
    """Retry 503 responses from the app under test.

    The backend answers 503 when an upstream provider (Supabase auth, the
    payment gateway) is briefly unavailable - the documented contract is
    "retry later". A flaky provider call must not fail the suite.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, attempts: int = 3, delay: float = 1.0):
        self._inner = inner
        self._attempts = attempts
        self._delay = delay

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._inner.handle_async_request(request)
        for attempt in range(self._attempts - 1):
            if response.status_code != 503:
                break
            await response.aclose()
            await asyncio.sleep(self._delay * (attempt + 1))
            response = await self._inner.handle_async_request(request)
        return response


@pytest.fixture(scope="session")
async def client():
    if TEST_DB.exists():
        TEST_DB.unlink()
    from backend.main import app
    from backend.db.database import init_db

    await init_db()
    transport = RetryOn503(ASGITransport(app=app))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver",
                                 timeout=30.0) as c:
        yield c
    # keep the file for post-mortem; CI can delete it


def pytest_collection_modifyitems(config, items):
    """Skip the DB-backed tests when Supabase is not configured.

    Without credentials every DB call raises, which buries real regressions
    under a wall of identical errors. Skipping keeps the signal clean. CI
    wires the credentials in (see .github/workflows/ci.yml), so the full suite
    actually runs there.
    """
    from backend.config import settings

    if settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY:
        return
    skip = pytest.mark.skip(
        reason="Supabase not configured (set SUPABASE_URL / SUPABASE_SECRET_KEY)"
    )
    for item in items:
        if "client" in getattr(item, "fixturenames", ()):
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def _skip_db_without_supabase(request):
    """Turn DB access into a skip when Supabase is not configured.

    The client factory is the single choke point every DB and auth call goes
    through, so tests that touch the database without the ``client`` fixture
    are skipped too instead of erroring out.
    """
    from backend.config import settings

    if settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY:
        return
    from backend.db import supabase as supabase_db

    async def _skip(*args, **kwargs):
        pytest.skip("Supabase not configured (set SUPABASE_URL / SUPABASE_SECRET_KEY)")

    mp = pytest.MonkeyPatch()
    mp.setattr(supabase_db, "create_async_client", _skip)
    request.addfinalizer(mp.undo)


def _purge_test_signals() -> None:
    """Remove signals written by test fixtures from the configured database.

    The suite runs against the real Supabase project (CI has no separate test
    project), and the fake engines tag their rows with ``{"src": "test"}``.
    Without this, every run leaves impossible entries such as EURUSD @ 100
    with SL 95 / TP 110 visible to real users.
    """
    from backend.config import settings

    if not (settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY):
        return
    headers = {
        "apikey": settings.SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
        "Prefer": "return=minimal",
    }
    url = (
        settings.SUPABASE_URL.rstrip("/")
        + "/rest/v1/signals?indicators->>src=eq.test"
    )
    try:
        with httpx.Client(timeout=30.0) as c:
            c.delete(url, headers=headers)
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _clean_test_signals():
    _purge_test_signals()
    yield
    _purge_test_signals()


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
