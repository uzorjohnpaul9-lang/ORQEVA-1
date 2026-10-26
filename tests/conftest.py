"""Test session setup: isolated DB, app client, shared helpers.

DASHBOARD_DATABASE_URL must be set BEFORE backend modules are imported.
"""
import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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


def _purge_test_users(created_after=None, older_than=None) -> None:
    """Delete ``@test.dev`` accounts from both Auth and the app database.

    Auth and ``public.users`` are separate stores, so a guard that only cleans
    one leaves the other polluted. The suite runs against production, and a
    single run used to leave ~1,250 Auth accounts behind.

    ``created_after`` scopes end-of-session cleanup to accounts made by this
    run. ``older_than`` clears leftovers from crashed runs while leaving a
    concurrently running suite alone.
    """
    from backend.config import settings

    key = settings.SUPABASE_SECRET_KEY
    if not (settings.SUPABASE_URL and key):
        return
    base = settings.SUPABASE_URL.rstrip("/")
    rest_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "return=minimal",
    }

    with httpx.Client(timeout=30.0, headers=rest_headers) as c:

        def call(method, url, **kwargs):
            response = None
            for attempt in range(4):
                try:
                    response = c.request(method, url, **kwargs)
                    if response.status_code not in (429, 500, 502, 503, 504):
                        return response
                except httpx.HTTPError:
                    response = None
                time.sleep(1.5 * (attempt + 1))
            return response

        r = call(
            "GET",
            base + "/rest/v1/users",
            params={
                "select": "id,email,created_at",
                "email": "like.*@test.dev",
                "limit": "10000",
            },
        )
        if r is None or r.status_code != 200:
            return

        # CI runners and Supabase can disagree by an hour or more. Translate the
        # local session boundaries onto the database clock instead of widening
        # the window and risking another suite's accounts.
        skew = timedelta(0)
        if r.headers.get("date"):
            server_now = parsedate_to_datetime(r.headers["date"])
            if server_now.tzinfo is None:
                server_now = server_now.replace(tzinfo=timezone.utc)
            skew = server_now - datetime.now(timezone.utc)
        start = created_after + skew if created_after else None
        stale = older_than + skew if older_than else None

        def wanted(user: dict) -> bool:
            raw = user.get("created_at")
            if not raw:
                return False
            created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if start is not None and created < start:
                return False
            if stale is not None and created >= stale:
                return False
            return True

        public_ids = [u["id"] for u in r.json() if wanted(u)]

        for i in range(0, len(public_ids), 20):
            chunk = public_ids[i : i + 20]
            ids = ",".join(chunk)
            call(
                "DELETE",
                base + "/rest/v1/notifications",
                params={"user_id": f"in.({ids})"},
            )
            call("DELETE", base + "/rest/v1/users", params={"id": f"in.({ids})"})

        auth_users = []
        page = 1
        while True:
            r = call(
                "GET",
                base + "/auth/v1/admin/users",
                params={"page": page, "per_page": 1000},
            )
            if r is None or r.status_code != 200:
                return
            batch = r.json().get("users", [])
            auth_users += [
                u
                for u in batch
                if (u.get("email") or "").lower().endswith("@test.dev")
                and wanted(u)
            ]
            if len(batch) < 1000:
                break
            page += 1

        for user in auth_users:
            call("DELETE", base + "/auth/v1/admin/users/" + user["id"])


_SESSION_START = datetime.now(timezone.utc)


@pytest.fixture(scope="session", autouse=True)
def _clean_test_signals():
    _purge_test_signals()
    yield
    _purge_test_signals()


@pytest.fixture(scope="session", autouse=True)
def _clean_test_users():
    _purge_test_users(older_than=_SESSION_START - timedelta(hours=2))
    yield
    # Allow for clock skew between the runner and Supabase, and for setup time
    # before the first account is created. CI serialises runs via `concurrency`.
    _purge_test_users(created_after=_SESSION_START - timedelta(minutes=10))


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
