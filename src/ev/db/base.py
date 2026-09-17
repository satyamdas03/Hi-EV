"""Hi-EV async database engine and declarative base.

`engine` and `SessionLocal` are exposed as module-level attributes but are
resolved lazily so that test fixtures can override `EV_DATABASE_URL` before the
engine is created.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import aiosqlite
import sqlite_vec
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ev.config import get_settings


def _to_async_url(url: str) -> str:
    """Convert a synchronous Postgres URL to an asyncpg URL if needed."""
    if url.startswith(("postgresql://", "postgres://")) and "+asyncpg" not in url:
        return url.replace("://", "+asyncpg://", 1)
    return url


def _raw_url() -> str:
    """Return the raw database URL, allowing EV_DATABASE_URL to override settings."""
    return os.environ.get("EV_DATABASE_URL") or get_settings().database_url


def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def _sqlite_async_creator(url: str):
    """Build an async_creator for aiosqlite that loads the sqlite-vec extension."""
    parsed = make_url(url)
    database = parsed.database or ":memory:"
    if database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)

    ext_path = sqlite_vec.loadable_path().replace("\\", "/")

    async def _creator():
        conn = await aiosqlite.connect(database)
        await conn.enable_load_extension(True)
        await conn.execute(f"SELECT load_extension('{ext_path}')")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    return _creator


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all Hi-EV ORM models."""


@lru_cache
def get_engine():
    """Return the async SQLAlchemy engine, created lazily on first call."""
    url = _to_async_url(_raw_url())
    if _is_sqlite_url(url):
        return create_async_engine(
            url,
            async_creator=_sqlite_async_creator(url),
            echo=False,
        )
    return create_async_engine(url, echo=False)


@lru_cache
def get_session_maker():
    """Return the async session maker, created lazily on first call."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def __getattr__(name: str):
    """Lazy module-level access to `engine` and `SessionLocal`."""
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_session_maker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
