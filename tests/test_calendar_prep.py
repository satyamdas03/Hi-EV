"""Tests for calendar prep tool."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.tools.calendar_prep_tool import CalendarPrepTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@patch("ev.tools.calendar_prep_tool.LLMClient")
async def test_calendar_prep_finds_deadlines_and_uses_llm(mock_llm, store):
    now = datetime.now(UTC)
    await store.upsert_deadlines([
        {"title": "Patent filing", "due_date": now + timedelta(hours=1), "source": "calendar", "source_id": "e1", "priority": "high"},
        {"title": "Doctor appointment", "due_date": now + timedelta(hours=3), "source": "calendar", "source_id": "e2", "priority": "medium"},
    ])

    llm = MagicMock()
    llm.complete = AsyncMock(return_value="You have a patent filing in 1 hour. Prepare the spec.")
    mock_llm.return_value = llm

    tool = CalendarPrepTool(window_hours=4)
    tool.bind_store(store)
    result = await tool.run(time=now.isoformat())

    assert "patent filing" in result["prep"].lower()
    assert "spec" in result["prep"]
    assert len(result["deadlines"]) == 2
    prompt = llm.complete.call_args.kwargs["messages"][0]["content"]
    assert "Patent filing" in prompt
