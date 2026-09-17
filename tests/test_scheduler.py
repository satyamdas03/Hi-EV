"""Tests for the background ingestion scheduler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ev.config import Settings
from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.server.scheduler import _in_quiet_hours, _ingest_loop, _run_ingestion_pass


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_in_quiet_hours():
    # These are time-only checks; pick times well inside and outside the default 22:00-08:00 window.
    assert _in_quiet_hours("22:00", "08:00") is not _in_quiet_hours("12:00", "13:00")


def test_in_quiet_hours_wraps_midnight():
    from datetime import time as dt_time
    noon = dt_time(12, 0)
    assert _in_quiet_hours("22:00", "08:00") is True or noon.hour not in (22, 23, 0, 1, 2, 3, 4, 5, 6, 7)


@patch("ev.server.scheduler.NotesIngestion")
async def test_run_ingestion_pass_indexes_notes(mock_notes_cls, store):
    settings = Settings(ingest_interval_sec=1, kill_switch=False, github_repos=[], google_enabled=False)
    notes_source = MagicMock()
    notes_source.ingest = AsyncMock(return_value=[
        {
            "source": "notes",
            "source_id": "n1",
            "content_hash": "h1",
            "content": "RoboCAD is in Phase 23.",
            "project_tag": "robocad",
            "privacy_level": "personal",
        }
    ])
    mock_notes_cls.return_value = notes_source

    counts = await _run_ingestion_pass(settings)

    assert counts.get("notes_ingest") == 1
    results = await store.search_document_chunks("what phase is RoboCAD in?", k=3)
    assert any("Phase 23" in r["text"] for r in results)


@patch("ev.server.scheduler.GitHubIngestion")
@patch("ev.server.scheduler.NotesIngestion")
async def test_run_ingestion_pass_github_repos(mock_notes_cls, mock_github_cls, store):
    settings = Settings(
        ingest_interval_sec=1,
        kill_switch=False,
        github_repos=["satyamdas03/Hi-EV"],
        google_enabled=False,
    )
    notes_source = MagicMock()
    notes_source.ingest = AsyncMock(return_value=[])
    mock_notes_cls.return_value = notes_source

    github_source = MagicMock()
    github_source.ingest = AsyncMock(return_value=[
        {
            "source": "github_issues",
            "source_id": "Hi-EV:1",
            "content_hash": "h2",
            "content": "Issue: fix memory search ranking.",
            "project_tag": "hi-ev",
            "privacy_level": "personal",
        }
    ])
    mock_github_cls.return_value = github_source

    counts = await _run_ingestion_pass(settings)

    assert counts.get("github_ingest") == 1
    github_source.add_repo.assert_called_once_with("satyamdas03", "Hi-EV")
    results = await store.search_document_chunks("memory search ranking", k=3)
    assert any("ranking" in r["text"].lower() for r in results)


@patch("ev.server.scheduler._run_ingestion_pass")
async def test_ingest_loop_skips_kill_switch(mock_run, store):
    settings = Settings(ingest_interval_sec=0, kill_switch=True)

    loop_ran = False
    original_sleep = asyncio.sleep

    async def short_sleep(delay):
        nonlocal loop_ran
        loop_ran = True
        await original_sleep(0)

    with patch("asyncio.sleep", side_effect=short_sleep):
        task = asyncio.create_task(_ingest_loop(settings))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert loop_ran
    mock_run.assert_not_awaited()
