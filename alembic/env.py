"""Async Alembic environment for Hi-EV."""

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from ev.config import get_settings
from ev.db.base import Base, get_engine

# This is the Alembic Config object.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate support.
target_metadata = Base.metadata


def _to_async_url(url: str) -> str:
    """Convert a synchronous Postgres URL to an asyncpg URL if needed."""
    if url.startswith(("postgresql://", "postgres://")) and "+asyncpg" not in url:
        return url.replace("://", "+asyncpg://", 1)
    return url


def _database_url() -> str:
    """Return the async URL for the configured database."""
    return _to_async_url(get_settings().database_url)


def include_object(object, name, type_, reflected, compare_to):
    """Skip sqlite-vec virtual tables that are not part of SQLAlchemy metadata."""
    if type_ == "table" and reflected:
        return name in Base.metadata.tables
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations against a connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the app engine.

    For SQLite, this ensures the sqlite-vec extension is loaded so that
    reflection of virtual tables does not break autogenerate.
    """
    connectable = get_engine()

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
