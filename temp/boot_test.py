import asyncio, httpx, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.main import app

async def main():
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=8011, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(4.0)
    async with httpx.AsyncClient(timeout=20) as c:
        try:
            r = await c.get("http://127.0.0.1:8011/api/health")
            print("HEALTH:", r.status_code, r.text)
        except Exception as e:
            print("HEALTH ERROR:", e)
        try:
            r = await c.get("http://127.0.0.1:8011/readyz")
            print("READYZ:", r.status_code, r.text[:400])
        except Exception as e:
            print("READYZ ERROR:", e)
    server.should_exit = True
    await asyncio.wait_for(task, timeout=10)

asyncio.run(main())