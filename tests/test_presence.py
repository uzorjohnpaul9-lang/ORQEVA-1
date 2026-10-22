"""Presence: online window and write throttling (no network)."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.db.models import USERS
from backend.services import presence_service


class FakeDB:
    def __init__(self):
        self.updates: list[tuple[str, dict, dict]] = []

    async def update(self, table: str, data: dict, where: dict | None = None):
        self.updates.append((table, data, where or {}))
        return [data]


class BrokenDB:
    async def update(self, *args, **kwargs):
        raise RuntimeError("column does not exist")


@pytest.fixture(autouse=True)
def clean_throttle():
    presence_service._last_touch.clear()
    yield
    presence_service._last_touch.clear()


def test_is_online_uses_window():
    now = datetime.now(timezone.utc)
    window = presence_service.ONLINE_WINDOW_SECONDS
    assert presence_service.is_online(now.isoformat(), now=now)
    assert presence_service.is_online((now - timedelta(seconds=window - 1)).isoformat(), now=now)
    assert not presence_service.is_online((now - timedelta(seconds=window + 1)).isoformat(), now=now)
    assert not presence_service.is_online(None, now=now)


def test_is_online_handles_naive_timestamps():
    now = datetime.now(timezone.utc)
    naive = now.replace(tzinfo=None).isoformat()
    assert presence_service.is_online(naive, now=now)


async def test_touch_writes_once_per_interval():
    db = FakeDB()
    assert await presence_service.touch(db, "u-1") is True
    assert await presence_service.touch(db, "u-1") is False
    assert len(db.updates) == 1
    table, data, where = db.updates[0]
    assert table == USERS
    assert where == {"id": "u-1"}
    assert data["last_seen_at"]


async def test_touch_never_raises():
    assert await presence_service.touch(BrokenDB(), "u-2") is False


async def test_touch_ignores_empty_user():
    assert await presence_service.touch(FakeDB(), "") is False
