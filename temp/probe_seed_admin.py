import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db.database import seed_admin

async def main():
    ok = await seed_admin()
    print("seed_admin ok:", ok)

asyncio.run(main())