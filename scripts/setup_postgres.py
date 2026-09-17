#!/usr/bin/env python3
"""Set up a local Postgres database with the pgvector extension for Hi-EV.

Run this after installing Postgres locally. It creates the `hiev` database and
enables the pgvector extension if they do not already exist.
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse

from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_ADMIN_URL = os.environ.get("EV_POSTGRES_ADMIN_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
DEFAULT_TARGET_DATABASE = "hiev"


async def database_exists(engine, name: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = :name",
            {"name": name},
        )
        return result.scalar_one_or_none() is not None


async def create_database(admin_url: str, name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        if await database_exists(engine, name):
            print(f"Database '{name}' already exists.")
            return
        async with engine.connect() as conn:
            await conn.execute(f"CREATE DATABASE {name}")
        print(f"Created database '{name}'.")
    finally:
        await engine.dispose()


async def enable_pgvector(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.commit()
        print("pgvector extension is enabled.")
    finally:
        await engine.dispose()


async def main():
    target_db = DEFAULT_TARGET_DATABASE
    parsed = urlparse(DEFAULT_ADMIN_URL)
    target_url = f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/{target_db}"

    print("Hi-EV Postgres setup")
    print(f"Admin URL: {DEFAULT_ADMIN_URL}")
    print(f"Target database: {target_db}")

    try:
        await create_database(DEFAULT_ADMIN_URL, target_db)
        await enable_pgvector(target_url)
    except (DBAPIError, OperationalError, ConnectionError, TimeoutError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "\nPostgres does not appear to be running or accessible. "
            "Install Postgres first:",
            file=sys.stderr,
        )
        print("  Windows: https://www.postgresql.org/download/windows/ or `winget install PostgreSQL.PostgreSQL`", file=sys.stderr)
        print("  WSL2:    sudo apt install postgresql postgresql-contrib", file=sys.stderr)
        print("  macOS:   brew install postgresql", file=sys.stderr)
        print("  Linux:   sudo apt install postgresql postgresql-contrib", file=sys.stderr)
        print("\nAfter installing, create a user/password and run this script again.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
