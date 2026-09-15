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


async def test_upsert_ingest_matches_source_pairs(store):
    """Regression: upsert must match the exact (source, source_id) pair, not mix them."""
    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:abc", "content_hash": "h1", "content": "feat: x", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_issues", "source_id": "RoboCAD:abc", "content_hash": "h2", "content": "bug: y", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_commits", "source_id": "RoboCAD:def", "content_hash": "h3", "content": "feat: z", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:abc", "content_hash": "h1", "content": "feat: x", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    assert await store.count_ingest_by_source("github_commits") == 2
    assert await store.count_ingest_by_source("github_issues") == 1


async def test_list_active_projects(store):
    await store.get_or_create_project("ActiveProj", active=True)
    await store.get_or_create_project("InactiveProj", active=False)
    active = await store.list_active_projects()
    assert {p.name for p in active} == {"ActiveProj"}


async def test_count_open_issues_and_prs(store):
    await store.get_or_create_project("RoboCAD")
    await store.upsert_ingest([
        {"source": "github_issues", "source_id": "RoboCAD:1", "content_hash": "h1", "content": "bug: mesh\nstate: open\n\nsteps", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_issues", "source_id": "RoboCAD:2", "content_hash": "h2", "content": "bug: ui\nstate: closed\n\nsteps", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_prs", "source_id": "RoboCAD:10", "content_hash": "h3", "content": "feat: x\nstate: open\n\nbody", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    assert await store.count_open_issues("RoboCAD") == 1
    assert await store.count_open_prs("RoboCAD") == 1


async def test_recent_notes(store):
    await store.get_or_create_project("RoboCAD")
    await store.upsert_ingest([
        {"source": "notes", "source_id": "n1", "content_hash": "h1", "content": "first note", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "notes", "source_id": "n2", "content_hash": "h2", "content": "second note", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_commits", "source_id": "RoboCAD:c1", "content_hash": "hc", "content": "commit", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    notes = await store.recent_notes("RoboCAD", limit=2)
    assert len(notes) == 2
    assert all(n.source == "notes" for n in notes)
