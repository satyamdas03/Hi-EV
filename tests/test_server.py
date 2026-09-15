import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def seeded_db():
    from ev.db.base import Base, SessionLocal, engine
    from ev.memory.store import MemoryStore
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
        await store.upsert_ingest([{
            "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
            "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
        }])
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_status_endpoint(seeded_db):
    from ev.server.api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/status", json={"project": "RoboCAD"})
        assert response.status_code == 200
        assert "RoboCAD" in response.json()["summary"]


async def test_brief_endpoint(seeded_db):
    from ev.server.api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/brief")
        assert response.status_code == 200
        data = response.json()
        assert "RoboCAD" in data["brief"]
        assert "active project" in data["brief"].lower()
