"""Tests for the Claude Code spawn tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Event
from ev.memory.store import MemoryStore
from ev.tools.work_tool import WorkTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@patch("ev.tools.work_tool.asyncio.create_subprocess_exec")
async def test_work_tool_spawns_claude_code_with_context(mock_create, store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_path="/repos/RoboCAD")
    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:c1", "content_hash": "h1", "content": "feat: gait controller", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "notes", "source_id": "n1", "content_hash": "h2", "content": "refactor plan", "project_tag": "robocad", "privacy_level": "personal"},
    ])

    process = MagicMock()
    process.stdin = MagicMock()
    process.stdin.drain = AsyncMock()
    process.stdout = MagicMock()
    process.stderr = MagicMock()
    process.pid = 12345
    mock_create.return_value = process

    tool = WorkTool()
    tool.bind_store(store)
    result = await tool.run(project="RoboCAD", task="refactor gait controller into a separate module")

    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    assert kwargs["cwd"] == "/repos/RoboCAD"
    assert args == ("claude", "code")
    written = process.stdin.write.call_args[0][0]
    assert isinstance(written, bytes)
    written_text = written.decode("utf-8")
    assert "refactor gait controller" in written_text
    assert "gait controller" in written_text
    assert "Phase 29" in written_text
    assert result["pid"] == 12345

    # Event logged
    event_result = await store.session.execute(select(Event).where(Event.event_type == "spawn_claude_code"))
    assert event_result.scalar_one_or_none() is not None


async def test_work_tool_requires_repo_path(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_path=None)
    tool = WorkTool()
    tool.bind_store(store)
    result = await tool.run(project="RoboCAD", task="do something")
    assert "repo path" in result["error"].lower()
