import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from ev.cli.main import cli
from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore


@pytest.fixture
async def seeded_store():
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


def test_status_command(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "RoboCAD"])
    assert result.exit_code == 0
    assert "RoboCAD" in result.output
    assert "Phase 29" in result.output


def test_status_json_command(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "RoboCAD", "--json"])
    assert result.exit_code == 0
    assert '"name": "RoboCAD"' in result.output
    assert '"phase": "Phase 29"' in result.output


def test_brief_command(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["brief"])
    assert result.exit_code == 0
    assert "RoboCAD" in result.output
    assert "active project" in result.output.lower()


@patch("ev.research.search.httpx.AsyncClient")
@patch("ev.tools.research_tool.LLMClient")
def test_research_command(mock_llm_client, mock_async_client):
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

    runner = CliRunner()
    result = runner.invoke(cli, ["research", "what is MPC"])
    assert result.exit_code == 0
    assert "Answer with citation" in result.output
    assert "https://example.com" in result.output
