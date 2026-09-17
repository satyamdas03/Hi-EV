"""Tests for the semantic memory search and remember tools."""

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.tools.memory_tool import MemoryTool, RememberTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_memory_tool_returns_formatted_text(store):
    await store.upsert_document_chunks([
        {"source": "user_memory", "source_id": "m1", "chunk_index": 0, "text": "RoboCAD is in Phase 23.", "project_name": "robocad"}
    ])

    tool = MemoryTool()
    tool.bind_store(store)
    result = await tool.run(query="what phase is RoboCAD in?")
    assert result["text"].startswith("EV remembers:")
    assert any("Phase 23" in c["text"] for c in result["chunks"])


async def test_memory_tool_empty_query(store):
    tool = MemoryTool()
    tool.bind_store(store)
    result = await tool.run(query="")
    assert "please provide a query" in result["text"]


async def test_remember_tool_stores_text(store):
    tool = RememberTool()
    tool.bind_store(store)
    result = await tool.run(text="RoboCAD is now in Phase 24.", project_name="robocad")
    assert "EV remembered that" in result["text"]
    assert result["ids"]

    # Search finds it.
    search = MemoryTool()
    search.bind_store(store)
    found = await search.run(query="what phase is RoboCAD in?")
    assert any("Phase 24" in c["text"] for c in found["chunks"])
