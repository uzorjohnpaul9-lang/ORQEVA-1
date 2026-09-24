"""Notifications + preferences."""
import httpx

from tests.conftest import register_and_login


async def test_notification_lifecycle(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)

    # trigger an event that creates a notification (kill switch)
    r = await client.post("/api/risk/kill-switch", headers=H,
                          json={"active": True, "reason": "notif test"})
    assert r.status_code == 200

    r = await client.get("/api/notifications", headers=H)
    body = r.json()
    assert any(n["type"] == "risk" for n in body["notifications"])
    unread_before = body["unread_count"]
    assert unread_before >= 1

    # read-all first (all notifications still unread here)
    r = await client.post("/api/notifications/read-all", headers=H)
    assert r.json()["marked"] >= 1
    assert (await client.get("/api/notifications/unread-count", headers=H)).json()["count"] == 0

    # marking an already-read one again is idempotent
    nid = body["notifications"][0]["id"]
    r = await client.post("/api/notifications/read", headers=H,
                          json={"notification_id": nid})
    assert r.status_code == 200


async def test_foreign_notification_hidden(client: httpx.AsyncClient):
    H1, _ = await register_and_login(client)
    H2, _ = await register_and_login(client)

    await client.post("/api/risk/kill-switch", headers=H1,
                      json={"active": True, "reason": "iso"})
    listing = (await client.get("/api/notifications", headers=H1)).json()
    nid = listing["notifications"][0]["id"]

    r = await client.post("/api/notifications/read", headers=H2,
                          json={"notification_id": nid})
    assert r.status_code == 404

    # H2 sees nothing of H1's events
    other = (await client.get("/api/notifications", headers=H2)).json()
    assert all(n["id"] != nid for n in other["notifications"])


async def test_preferences_crud_and_validation(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)

    p = (await client.get("/api/preferences", headers=H)).json()
    assert p["telegram_signals"] is True and p["telegram_linked"] is False

    r = await client.put("/api/preferences", headers=H,
                         json={"default_market": "crypto", "risk_tolerance": "aggressive"})
    assert r.json()["default_market"] == "crypto"

    r = await client.put("/api/preferences", headers=H,
                         json={"risk_tolerance": "yolo"})
    assert r.status_code == 422


async def test_telegram_link_unlink(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)

    r = await client.post("/api/preferences/telegram/link", headers=H,
                          json={"chat_id": "123456789"})
    assert r.status_code == 200
    assert r.json()["telegram_chat_id"] == "123456789"

    r = await client.delete("/api/preferences/telegram/link", headers=H)
    assert r.json()["telegram_linked"] is False
