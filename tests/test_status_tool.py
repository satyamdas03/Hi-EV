import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_status_tool_returns_summary(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
    await store.upsert_ingest([{
        "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
        "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
    }])
    registry = ToolRegistry(store)
    registry.register(StatusTool())
    result = await registry.get("status").run(project="RoboCAD")
    assert "Phase 29" in result
    assert "deliver Phase 29" in result
