from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient


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


@patch("ev.tools.work_tool.asyncio.create_subprocess_exec")
async def test_work_endpoint(mock_create, seeded_db):
    from ev.server.api import app
    process = MagicMock()
    process.stdin = MagicMock()
    process.stdin.drain = AsyncMock()
    process.stdout = MagicMock()
    process.stderr = MagicMock()
    process.pid = 1234
    mock_create.return_value = process

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


@patch("ev.tools.draft_tools.LLMClient")
@patch("ev.tools.draft_tools.subprocess.run")
async def test_draft_endpoint(mock_run, mock_llm, seeded_db):
    from ev.server.api import app
    mock_run.return_value = MagicMock(stdout="diff --git a/x.py b/x.py\n+def f(): pass", stderr="", returncode=0)
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="feat: add f")
    mock_llm.return_value = llm

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/draft", json={"type": "commit", "project": "RoboCAD"})
        assert response.status_code == 200
        data = response.json()
        assert "feat: add f" in data["draft"]


@patch("ev.tools.calendar_prep_tool.LLMClient")
async def test_calendar_prep_endpoint(mock_llm, seeded_db):
    from datetime import UTC, datetime, timedelta

    from ev.db.base import SessionLocal
    from ev.server.api import app

    async with SessionLocal() as session:
        from ev.memory.store import MemoryStore
        store = MemoryStore(session)
        await store.upsert_deadlines([{
            "title": "Review call", "due_date": datetime.now(UTC) + timedelta(hours=1),
            "source": "calendar", "source_id": "cal1", "priority": "high"
        }])

    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Review call prep packet.")
    mock_llm.return_value = llm

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/calendar-prep", json={"time": datetime.now(UTC).isoformat()})
        assert response.status_code == 200
        data = response.json()
        assert "Review call prep packet" in data["prep"]


def test_websocket_ping():
    """A WebSocket connection can be opened and receives a heartbeat."""
    from fastapi.testclient import TestClient

    from ev.server.api import app

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "ping"})
        data = ws.receive_json()
        assert data["type"] == "pong"


def test_focus_endpoint_notifies_clients():
    """POST /focus sends a focus event to every connected WebSocket client."""
    from fastapi.testclient import TestClient

    from ev.server.api import app

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        response = client.post("/focus")
        assert response.status_code == 200
        data = response.json()
        assert data["focused"] is True
        assert data["clients"] >= 1
        focus = ws.receive_json()
        assert focus["type"] == "focus"
