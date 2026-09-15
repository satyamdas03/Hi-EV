"""Tests for the cross-project brief tool."""

from datetime import UTC, datetime, timedelta

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Ingest
from ev.memory.store import MemoryStore
from ev.tools.brief_tool import BriefTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_brief_mentions_active_projects_and_highlights_stale(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29", active=True)
    await store.get_or_create_project("HiEV", current_phase="Phase 2", active=True)
    await store.get_or_create_project("OldProj", current_phase="Phase 1", active=True)

    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:c1", "content_hash": "h1", "content": "feat: x", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_commits", "source_id": "HiEV:c1", "content_hash": "h2", "content": "feat: y", "project_tag": "hiev", "privacy_level": "personal"},
    ])

    # Make OldProj's only activity stale (> stale_days threshold).
    old = Ingest(
        source="github_commits",
        source_id="OldProj:c1",
        content_hash="h3",
        content="old commit",
        project_tag="oldproj",
        privacy_level="personal",
        updated_at=datetime.now(UTC) - timedelta(days=30),
    )
    store.session.add(old)
    await store.session.commit()

    tool = BriefTool(stale_days=7)
    tool.bind_store(store)
    brief = await tool.run()

    assert "RoboCAD" in brief and "Phase 29" in brief
    assert "HiEV" in brief and "Phase 2" in brief
    assert "OldProj" in brief
    assert "stale" in brief.lower()


async def test_brief_ignores_inactive_projects(store):
    await store.get_or_create_project("Active", current_phase="Phase 1", active=True)
    await store.get_or_create_project("Inactive", current_phase="Phase 0", active=False)

    tool = BriefTool(stale_days=7)
    tool.bind_store(store)
    brief = await tool.run()

    assert "Active" in brief
    assert "Inactive" not in brief
