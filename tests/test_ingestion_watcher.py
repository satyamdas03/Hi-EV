"""Tests for the file-system watcher incremental ingestion."""

from __future__ import annotations

import asyncio

import pytest

from ev.config import Settings
from ev.db.base import Base, SessionLocal, engine, get_engine, get_session_maker
from ev.ingestion.watcher import VaultWatcher
from ev.memory.store import MemoryStore


def _reset_db_engine():
    """Clear cached engines/session makers so each test gets its own database."""
    get_engine.cache_clear()
    get_session_maker.cache_clear()


@pytest.fixture
async def watcher(tmp_path, monkeypatch):
    """Provide an isolated watcher over a temp notes directory."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'hiev.db'}"
    monkeypatch.setenv("EV_DATABASE_URL", db_url)
    _reset_db_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    settings = Settings(
        notes_path=tmp_path,
        personal_only=True,
        database_url=db_url,
        robocad_path=None,
        learningrobotics_path=None,
        hiev_path=None,
    )
    watcher = VaultWatcher(settings)
    await watcher.start()
    yield watcher, tmp_path
    await watcher.stop()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    _reset_db_engine()


async def _wait_for_ingest_count(
    source: str, expected: int, timeout: float = 15.0
) -> int:
    """Poll the DB until the ingest count matches expected or timeout elapses."""
    deadline = asyncio.get_event_loop().time() + timeout
    count = 0
    while asyncio.get_event_loop().time() < deadline:
        async with SessionLocal() as session:
            store = MemoryStore(session)
            count = await store.count_ingest_by_source(source)
            if count == expected:
                return count
        await asyncio.sleep(0.5)
    return count


async def test_watcher_ingests_new_note(watcher):
    _, root = watcher
    note = root / "robocad.md"
    note.write_text("# RoboCAD\nPhase G2 watcher works.", encoding="utf-8")

    count = await _wait_for_ingest_count("notes", 1)
    assert count == 1

    async with SessionLocal() as session:
        store = MemoryStore(session)
        chunks = await store.search_document_chunks("Phase G2 watcher", k=5)
        assert any("watcher works" in c["text"] for c in chunks)


async def test_watcher_re_ingests_modified_note(watcher):
    _, root = watcher
    note = root / "robocad.md"
    note.write_text("# RoboCAD\nOriginal content.", encoding="utf-8")

    count = await _wait_for_ingest_count("notes", 1)
    assert count == 1

    note.write_text("# RoboCAD\nUpdated content for G2.", encoding="utf-8")

    found = False
    deadline = asyncio.get_event_loop().time() + 15.0
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
        async with SessionLocal() as session:
            store = MemoryStore(session)
            chunks = await store.search_document_chunks("Updated content for G2", k=5)
            if any("Updated content for G2" in c["text"] for c in chunks):
                found = True
                break
    assert found


async def test_watcher_deletes_removed_note(watcher):
    _, root = watcher
    note = root / "robocad.md"
    note.write_text("# RoboCAD\nTo be deleted.", encoding="utf-8")

    count = await _wait_for_ingest_count("notes", 1)
    assert count == 1

    note.unlink()

    deadline = asyncio.get_event_loop().time() + 15.0
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
        async with SessionLocal() as session:
            store = MemoryStore(session)
            count = await store.count_ingest_by_source("notes")
            chunks = await store.search_document_chunks("To be deleted", k=5)
            if count == 0 and not any("To be deleted" in c["text"] for c in chunks):
                return

    pytest.fail("Deleted note was not removed from memory")


async def test_watcher_no_paths_is_noop(tmp_path):
    """A watcher with no valid paths should start/stop without error."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        settings = Settings(
            notes_path=tmp_path / "does_not_exist",
            personal_only=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'hiev.db'}",
        )
        watcher = VaultWatcher(settings)
        await watcher.start()
        await watcher.stop()
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


async def test_watcher_ignores_non_md_files(watcher):
    _, root = watcher
    (root / "robocad.txt").write_text("plain text note", encoding="utf-8")
    (root / "robocad.md").write_text("# RoboCAD\nmarkdown note", encoding="utf-8")

    count = await _wait_for_ingest_count("notes", 1)
    assert count == 1

    async with SessionLocal() as session:
        store = MemoryStore(session)
        records = await store.recent_notes("robocad", limit=5)
        assert all(str(r.source_id).endswith(".md") for r in records)
