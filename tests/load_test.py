"""Simple asyncio load harness (Phase 17).

Run against a LIVE server:  python tests/load_test.py [concurrency] [duration_s]
Not part of the pytest run - it needs a running uvicorn instance.
"""
import asyncio
import sys
import time

import httpx

BASE = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8001"


async def worker(client: httpx.AsyncClient, stop_at: float, results: list):
    email = f"load{time.time_ns()}@test.dev"
    try:
        await client.post("/api/auth/register", json={
            "email": email, "username": email.split("@")[0], "password": "Loadpass123!"})
        r = await client.post("/api/auth/login", json={"email": email, "password": "Loadpass123!"})
        if r.status_code != 200:
            results.append((r.status_code, 0.0))
            return
    except Exception as e:
        print(f"worker setup failed ({type(e).__name__}), continuing with fewer workers")
        return
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    while time.time() < stop_at:
        t0 = time.perf_counter()
        paths = [
            ("GET", "/api/health", None),
            ("GET", "/api/dashboard/overview", H),
            ("GET", "/api/notifications/unread-count", H),
            ("GET", "/api/preferences", H),
        ]
        method, path, headers = paths[time.monotonic_ns() % len(paths)]
        try:
            resp = await client.request(method, path, headers=headers)
            results.append((resp.status_code, time.perf_counter() - t0))
        except Exception:
            results.append((0, time.perf_counter() - t0))


async def main(concurrency: int, duration: float):
    results: list = []
    limits = httpx.Limits(max_connections=concurrency + 5,
                          max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=BASE, timeout=30, limits=limits) as client:
        stop_at = time.time() + duration
        await asyncio.gather(*(worker(client, stop_at, results) for _ in range(concurrency)))

    ok = [r for r in results if 200 <= r[0] < 300]
    err = [r for r in results if not 200 <= r[0] < 300]
    lat = sorted(r[1] for r in ok)
    p50 = lat[len(lat) // 2] * 1000 if lat else 0
    p95 = lat[int(len(lat) * 0.95)] * 1000 if lat else 0
    print(f"requests={len(results)} ok={len(ok)} err={len(err)} "
          f"p50={p50:.1f}ms p95={p95:.1f}ms throughput={len(results) / duration:.1f}rps")
    codes = {}
    for code, _ in err:
        codes[code] = codes.get(code, 0) + 1
    if codes:
        print("error codes:", codes)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    d = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    asyncio.run(main(n, d))
