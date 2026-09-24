"""Billing lifecycle: promos, invoices, approve/reject/refund, tier sync."""
import uuid

import httpx

from tests.conftest import register_and_login, make_admin


async def _admin_promo(client, AH, pct=25):
    code = f"T{uuid.uuid4().hex[:8].upper()}"
    r = await client.post("/api/billing/admin/promos", headers=AH,
                          json={"code": code, "discount_pct": pct})
    assert r.status_code in (200, 201), r.text
    return code


async def _invoice(client, H, AH, tier="premium"):
    code = await _admin_promo(client, AH)
    r = await client.post("/api/billing/invoices", headers=H,
                          json={"tier": tier, "method": "manual", "promo_code": code})
    assert r.status_code in (200, 201), r.text
    inv = r.json()
    r = await client.post(f"/api/billing/invoices/{inv['id']}/tx-ref", headers=H,
                          json={"tx_ref": f"TX-{uuid.uuid4().hex[:10]}"})
    assert r.status_code == 200, r.text
    return inv


async def test_full_approve_and_refund_cycle(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    AH, _ = await make_admin(client)

    inv = await _invoice(client, H, AH)

    r = await client.post(f"/api/billing/admin/invoices/{inv['id']}/approve", headers=AH)
    assert r.status_code == 200, r.text

    me = (await client.get("/api/auth/me", headers=H)).json()
    assert me["tier"] == "premium"

    sub = await client.get("/api/billing/subscription", headers=H)
    assert sub.status_code == 200 and sub.json()["tier"] == "premium"

    r = await client.post(f"/api/billing/admin/invoices/{inv['id']}/refund", headers=AH,
                          json={"reason": "test refund"})
    assert r.status_code == 200

    me = (await client.get("/api/auth/me", headers=H)).json()
    assert me["tier"] == "free"


async def test_reject_flow(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    AH, _ = await make_admin(client)
    inv = await _invoice(client, H, AH)

    r = await client.post(f"/api/billing/admin/invoices/{inv['id']}/reject", headers=AH,
                          json={"reason": "bad proof"})
    assert r.status_code == 200
    me = (await client.get("/api/auth/me", headers=H)).json()
    assert me["tier"] == "free"

    # double-processing rejected
    r = await client.post(f"/api/billing/admin/invoices/{inv['id']}/approve", headers=AH)
    assert r.status_code == 400


async def test_non_admin_cannot_process(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    AH, _ = await make_admin(client)
    inv = await _invoice(client, H, AH)

    r = await client.post(f"/api/billing/admin/invoices/{inv['id']}/approve", headers=H)
    assert r.status_code == 403


async def test_invalid_tier_rejected(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    r = await client.post("/api/billing/invoices", headers=H,
                          json={"tier": "diamond", "method": "manual"})
    assert r.status_code in (400, 422)


async def test_bad_promo_discounted_price(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    AH, _ = await make_admin(client)
    code = await _admin_promo(client, AH, pct=50)

    r_no = await client.post("/api/billing/invoices", headers=H,
                             json={"tier": "vip", "method": "manual"})
    r_yes = await client.post("/api/billing/invoices", headers=H,
                              json={"tier": "vip", "method": "manual", "promo_code": code})
    assert float(r_no.json()["amount_usd"]) > float(r_yes.json()["amount_usd"])
