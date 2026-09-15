import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_upsert_ingest_idempotent(store):
    records = [
        {"source": "github_commits", "source_id": "RoboCAD:abc", "content_hash": "h1", "content": "feat: x", "project_tag": "robocad", "privacy_level": "personal"}
    ]
    await store.upsert_ingest(records)
    await store.upsert_ingest(records)
    count = await store.count_ingest_by_source("github_commits")
    assert count == 1
