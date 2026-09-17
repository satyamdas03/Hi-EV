"""Hi-EV async database engine and declarative base.

`engine` and `SessionLocal` are exposed as module-level attributes but are
resolved lazily so that test fixtures can override `EV_DATABASE_URL` before the
engine is created.
"""

from __future__ import annotations

import os
from functools import lru_cache

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


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all Hi-EV ORM models."""


@lru_cache
def get_engine():
    """Return the async SQLAlchemy engine, created lazily on first call."""
    return create_async_engine(_to_async_url(_raw_url()), echo=False)


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
