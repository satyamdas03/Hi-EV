import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
async def seeded_db():
    from ev.db.base import Base, SessionLocal, engine
    from ev.memory.store import MemoryStore
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_path="/repos/RoboCAD")
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


@patch("ev.tools.work_tool.subprocess.Popen")
async def test_work_endpoint(mock_popen, seeded_db):
    from ev.server.api import app
    process = MagicMock()
    process.stdin = MagicMock()
    process.stdout = MagicMock()
    process.stderr = MagicMock()
    process.pid = 1234
    mock_popen.return_value = process

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/work", json={"project": "RoboCAD", "task": "fix test"})
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "RoboCAD"
        assert data["pid"] == 1234


@patch("ev.research.search.httpx.AsyncClient")
@patch("ev.tools.research_tool.LLMClient")
async def test_research_endpoint(mock_llm_client, mock_async_client, seeded_db):
    from ev.server.api import app
    response = MagicMock()
    response.status_code = 200
    response.text = '<div class="result results_links_deep web-result"><div class="links_main links_deep result__body"><h2 class="result__title"><a class="result__a" href="https://example.com">Title</a></h2><a class="result__url" href="https://example.com">example.com</a><a class="result__snippet">Snippet text.</a></div></div>'
    response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=response)
    mock_async_client.return_value = mock_client

    llm_instance = MagicMock()
    llm_instance.complete = AsyncMock(return_value="Answer with citation [1].")
    mock_llm_client.return_value = llm_instance

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/research", json={"query": "what is MPC"})
        assert response.status_code == 200
        data = response.json()
        assert "Answer with citation" in data["answer"]
        assert any(s["url"] == "https://example.com" for s in data["sources"])
