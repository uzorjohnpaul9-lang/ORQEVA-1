"""Adapter registry unit tests + security headers/CORS."""
import base64
import json
import urllib.parse

import httpx

from tests.conftest import register_and_login


def test_kraken_signature_deterministic_and_nonce_sensitive():
    from backend.exchanges.kraken_adapter import KrakenAdapter

    secret = base64.b64encode(b"k" * 64).decode()
    s1 = KrakenAdapter._sign(secret, "/0/private/Balance", "1000", "nonce=1000")
    s2 = KrakenAdapter._sign(secret, "/0/private/Balance", "1000", "nonce=1000")
    s3 = KrakenAdapter._sign(secret, "/0/private/Balance", "2000", "nonce=2000")
    assert s1 == s2 and s1 != s3 and len(s1) > 80


def test_coinbase_jwt_shape():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from backend.exchanges.coinbase_adapter import CoinbaseAdapter

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    token = CoinbaseAdapter()._jwt("orgs/kid-1", pem)[0]
    h_b64 = token.split(".")[0]
    header = json.loads(base64.urlsafe_b64decode(h_b64 + "=" * (-len(h_b64) % 4)))
    assert header["alg"] == "ES256" and header["kid"] == "orgs/kid-1"


def test_oanda_host_selection():
    from backend.exchanges.oanda_adapter import OandaAdapter

    a = OandaAdapter()
    assert "fxpractice" in a._base(True)
    assert "fxtrade" in a._base(False)


async def test_exchange_meta_and_connect_validation(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)

    r = await client.get("/api/exchanges/meta", headers=H)
    names = {a["name"] for a in r.json()}
    assert {"alpaca", "kraken", "oanda", "coinbase"} <= names

    # fake kraken creds: connect succeeds, validation fails -> stored inactive
    r = await client.post("/api/exchanges/connect", headers=H, json={
        "exchange": "kraken",
        "api_key": "FAKEKEY123456",
        "api_secret": base64.b64encode(b"x" * 40).decode(),
        "is_paper": False,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["is_active"] is False and body["validation"]["ok"] is False


async def test_security_headers(client: httpx.AsyncClient):
    r = await client.get("/api/health")
    h = r.headers
    assert h.get("x-content-type-options") == "nosniff"
    assert h.get("x-frame-options") == "DENY"
    assert "default-src 'none'" in (h.get("content-security-policy") or "")
    assert h.get("cache-control") == "no-store"


async def test_cors_origin_rules(client: httpx.AsyncClient):
    r = await client.options("/api/health", headers={
        "Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "http://evil.example"

    r = await client.options("/api/health", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
