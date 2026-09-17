from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_path="/repos/RoboCAD")
        await store.upsert_ingest([{
            "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
            "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
        }])
        await store.upsert_deadlines([{
            "title": "Stand-up prep", "due_date": datetime.now(UTC) + timedelta(hours=1),
            "source": "calendar", "source_id": "cal1", "priority": "medium"
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


@patch("ev.tools.work_tool.asyncio.create_subprocess_exec")
def test_work_command(mock_create, seeded_store):
    process = MagicMock()
    process.stdin = MagicMock()
    process.stdin.drain = AsyncMock()
    process.stdout = MagicMock()
    process.stderr = MagicMock()
    process.pid = 1234
    mock_create.return_value = process

    runner = CliRunner()
    result = runner.invoke(cli, ["work", "on", "fix failing test in Phase 29", "--project", "RoboCAD"])
    assert result.exit_code == 0
    assert "RoboCAD" in result.output
    assert "1234" in result.output
    mock_create.assert_called_once()


@patch("ev.tools.draft_tools.LLMClient")
@patch("ev.tools.draft_tools.subprocess.run")
def test_draft_commit_command(mock_run, mock_llm, seeded_store):
    mock_run.return_value = MagicMock(stdout="diff --git a/x.py b/x.py\n+def f(): pass", stderr="", returncode=0)
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="feat: add f")
    mock_llm.return_value = llm

    runner = CliRunner()
    result = runner.invoke(cli, ["draft", "commit", "--project", "RoboCAD"])
    assert result.exit_code == 0
    assert "feat: add f" in result.output


@patch("ev.tools.draft_tools.LLMClient")
@patch("ev.tools.draft_tools.subprocess.run")
def test_draft_pr_command(mock_run, mock_llm, seeded_store):
    mock_run.return_value = MagicMock(stdout="diff --git a/y.py b/y.py\n+def g(): pass", stderr="", returncode=0)
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Title: Add g\n\nBody: adds g")
    mock_llm.return_value = llm

    runner = CliRunner()
    result = runner.invoke(cli, ["draft", "pr", "--project", "RoboCAD"])
    assert result.exit_code == 0
    assert "Add g" in result.output


@patch("ev.tools.draft_tools.LLMClient")
def test_draft_reply_command(mock_llm):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Thanks, let's talk soon.")
    mock_llm.return_value = llm

    runner = CliRunner()
    result = runner.invoke(cli, ["draft", "reply", "--to", "recruiter@example.com", "--subject", "Role", "--snippet", "We have a role"])
    assert result.exit_code == 0
    assert "Thanks, let's talk soon" in result.output


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


@patch("ev.tools.calendar_prep_tool.LLMClient")
def test_calendar_prep_command(mock_llm, seeded_store):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Prepare stand-up notes.")
    mock_llm.return_value = llm

    runner = CliRunner()
    result = runner.invoke(cli, ["calendar", "prep", datetime.now(UTC).isoformat()])
    assert result.exit_code == 0
    assert "Prepare stand-up notes" in result.output


def test_remember_command(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["remember", "RoboCAD is in Phase 23."])
    assert result.exit_code == 0
    assert "EV remembered that" in result.output


def test_remember_command_with_project(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["remember", "RoboCAD milestone reached.", "--project", "RoboCAD"])
    assert result.exit_code == 0
    assert "EV remembered that" in result.output
