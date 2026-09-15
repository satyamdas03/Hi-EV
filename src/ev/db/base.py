"""Hi-EV async database engine and declarative base."""

import os

from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ev.config import get_settings


def _to_async_url(url: str) -> str:
    """Convert a synchronous Postgres URL to an asyncpg URL if needed."""
    if url.startswith(("postgresql://", "postgres://")) and "+asyncpg" not in url:
        return url.replace("://", "+asyncpg://", 1)
    return url


# Allow EV_DATABASE_URL to override the configured settings URL for tests and
# one-off scripts. In production, get_settings().database_url is the source of
# truth when no environment override is present.
_raw_url = os.environ.get("EV_DATABASE_URL") or get_settings().database_url
DATABASE_URL = _to_async_url(_raw_url)


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all Hi-EV ORM models."""


engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
