"""Broker bridge health transitions and alert throttling."""
import pytest

from backend.services import broker_health_service as svc


@pytest.fixture(autouse=True)
def _clean_state():
    svc.reset()
    yield
    svc.reset()


def test_next_action_transitions():
    now = 1000.0
    assert svc._next_action(None, True, now, 3600) is None
    assert svc._next_action(None, False, now, 3600) == "down"
    assert svc._next_action({"ok": True}, False, now, 3600) == "down"
    assert svc._next_action({"ok": False, "alerted_at": 900}, True, now, 3600) == "recovered"
    assert svc._next_action({"ok": False, "alerted_at": 900}, False, now, 3600) is None
    assert svc._next_action({"ok": False, "alerted_at": 100}, False, 5000.0, 3600) == "down"


def test_status_without_checks():
    assert svc.status() == {"checked": False}


class _FakeAdapter:
    def __init__(self, results):
        self._results = list(results)

    def health(self):
        return self._results.pop(0)


class _FakeDB:
    def __init__(self, conn, user):
        self.conn = conn
        self.user = user

    async def fetch_all(self, *args, **kwargs):
        return [self.conn]

    async def fetch_one(self, *args, **kwargs):
        return self.user


async def test_check_alerts_on_down_then_recovery(monkeypatch):
    alerts = []

    async def fake_alert(db, conn, ok, detail):
        alerts.append((ok, detail))
        return True

    monkeypatch.setattr(svc, "_send_alert", fake_alert)
    adapter = _FakeAdapter([
        {"ok": False, "reachable": False, "mt5_available": None, "detail": "dns"},
        {"ok": False, "reachable": False, "mt5_available": None, "detail": "dns"},
        {"ok": True, "reachable": True, "mt5_available": True, "detail": None},
    ])
    monkeypatch.setattr(svc, "get_adapter", lambda name: adapter)
    db = _FakeDB(
        {"id": "c1", "exchange": "exness", "is_paper": False, "user_id": "u1"},
        {"id": "u1", "tier": "premium", "telegram_chat_id": None},
    )

    first = await svc.check_and_alert(db)
    assert first == {"checked": 1, "down": 1, "alerts": 1}
    assert alerts == [(False, "dns")]

    second = await svc.check_and_alert(db)
    assert second == {"checked": 1, "down": 1, "alerts": 0}
    assert len(alerts) == 1

    third = await svc.check_and_alert(db)
    assert third == {"checked": 1, "down": 0, "alerts": 1}
    assert alerts[-1] == (True, None)

    state = svc.status()
    assert state["checked"] is True
    assert state["reachable"] is True
    assert state["down_connections"] == 0


async def test_paper_and_unsupported_adapters_are_skipped(monkeypatch):
    calls = []

    class _Unsupported:
        def health(self):
            calls.append("health")
            return {"ok": True, "reachable": None, "mt5_available": None, "detail": ""}

    monkeypatch.setattr(svc, "get_adapter", lambda name: _Unsupported())
    db = _FakeDB(
        {"id": "c1", "exchange": "exness", "is_paper": False, "user_id": "u1"},
        {"id": "u1", "tier": "premium", "telegram_chat_id": None},
    )
    out = await svc.check_and_alert(db)
    assert out == {"checked": 0, "down": 0, "alerts": 0}
    assert svc.status() == {"checked": False}
