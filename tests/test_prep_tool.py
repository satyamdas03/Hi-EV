"""Tests for the meeting prep tool."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Ingest
from ev.memory.store import MemoryStore
from ev.tools.prep_tool import PrepTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@patch("ev.tools.prep_tool.LLMClient")
async def test_prep_tool_includes_memory_context(mock_llm, store):
    now = datetime.now(UTC)
    event = Ingest(
        source="calendar_events",
        source_id="cal1",
        content_hash="h1",
        content="Event: RoboCAD sync\nStart: " + now.isoformat() + "\nAttendees: alice@example.com",
        project_tag="robocad",
        privacy_level="personal",
        updated_at=now,
    )
    store.session.add(event)
    await store.session.commit()

    await store.upsert_document_chunks([
        {"source": "user_memory", "source_id": "m1", "chunk_index": 0,
         "text": "RoboCAD sync should discuss the new humanoid gait controller.", "project_name": "robocad"}
    ])

    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Discuss the gait controller.")
    mock_llm.return_value = llm

    tool = PrepTool(window_hours=1)
    tool.bind_store(store)
    result = await tool.run(title="RoboCAD sync", project_name="robocad", time=now.isoformat())

    assert "gait controller" in result["prep"].lower()
    prompt = llm.complete.call_args.kwargs["messages"][0]["content"]
    assert "Related memory" in prompt
    assert "humanoid gait controller" in prompt
