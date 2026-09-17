"""Set up the default Hi-EV SQLite database with sqlite-vec enabled.

This is the zero-intervention path: no Postgres install is required.
Run this after `pip install -e ".[dev]"` to create the local DB, apply
Alembic migrations, and create the sqlite-vec virtual table.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import make_url

from ev.config import get_settings
from ev.db.base import engine
from ev.db.vector import create_vector_table


def _ensure_parent_dir(url: str) -> None:
    parsed = make_url(url)
    database = parsed.database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    settings = get_settings()
    url = settings.database_url

    if not url.startswith("sqlite"):
        print(f"WARNING: EV_DATABASE_URL is not SQLite ({url}).")
        print("This script is meant for the default sqlite-vec path.")

    _ensure_parent_dir(url)

    print("Applying Alembic migrations...")
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "alembic", "upgrade", "head"
    )
    returncode = await proc.wait()
    if returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed with exit code {returncode}")

    print("Creating sqlite-vec vector table...")
    async with engine.connect() as conn:
        await create_vector_table(conn)
    await engine.dispose()

    print(f"Hi-EV SQLite database is ready: {url}")


if __name__ == "__main__":
    asyncio.run(main())
