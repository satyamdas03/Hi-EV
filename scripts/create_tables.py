"""Create all Hi-EV tables from SQLAlchemy metadata."""

import asyncio

from ev.db.base import Base, engine


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")


if __name__ == "__main__":
    asyncio.run(main())
