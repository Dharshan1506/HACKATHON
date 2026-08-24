import asyncio
from app.database.connection import init_db, AsyncSessionLocal
from app.api.router import seed_demo_data

async def run_seed():
    print("Initializing database tables...")
    await init_db()
    async with AsyncSessionLocal() as session:
        print("Seeding sample packaged commodity compliance reports...")
        res = await seed_demo_data(session)
        print(res)

if __name__ == "__main__":
    asyncio.run(run_seed())
