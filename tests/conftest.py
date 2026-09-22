"""Shared pytest fixtures for the Hi-EV test suite."""

import os
import tempfile
from contextlib import suppress
from pathlib import Path

import pytest


def pytest_configure(config):
    """Force tests to use a shared file-based SQLite database.

    A file DB lets async REST endpoint tests and direct store tests see the
    same data, while the engine is created once per session and reused.
    """
    db_path = Path(tempfile.gettempdir()) / f"hiev_test_{os.getpid()}.db"
    os.environ["EV_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    # ev.db.base may have been imported by pytest plugins; clear the cached
    # engine/session maker so the test URL wins.
    with suppress(Exception):
        from ev.db.base import get_engine, get_session_maker

        get_engine.cache_clear()
        get_session_maker.cache_clear()
    with suppress(Exception):
        from ev.config import get_settings

        get_settings.cache_clear()


def pytest_sessionfinish(session, exitstatus):
    """Dispose the shared async engine and remove the temp database."""
    with suppress(Exception):
        import asyncio

        from ev.db.base import engine

        asyncio.run(engine.dispose())
    db_path = Path(tempfile.gettempdir()) / f"hiev_test_{os.getpid()}.db"
    with suppress(Exception):
        db_path.unlink(missing_ok=True)


@pytest.fixture
async def seeded_db():
    from ev.db.base import Base, SessionLocal, engine
    from ev.memory.store import MemoryStore
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_path="/repos/RoboCAD")
        await store.upsert_ingest([{
            "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
            "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
        }])
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
