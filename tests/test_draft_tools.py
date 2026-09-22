"""Tests for Tier-2 consequential drafting tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Event
from ev.memory.store import MemoryStore
from ev.tools.draft_tools import DraftCommitTool, DraftPrTool, DraftReplyTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@patch("ev.tools.draft_tools.LLMClient")
@patch("ev.tools.draft_tools.subprocess.run")
async def test_draft_commit_from_staged_diff(mock_run, mock_llm, store):
    mock_run.return_value = MagicMock(stdout="diff --git a/x.py b/x.py\n+def solver(): pass", stderr="", returncode=0)
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="feat: add solver stub")
    mock_llm.return_value = llm

    await store.get_or_create_project("RoboCAD", repo_path="/repos/RoboCAD")
    tool = DraftCommitTool()
    tool.bind_store(store)
    result = await tool.run(project="RoboCAD")

    assert "feat: add solver stub" in result["draft"]
    assert result["tier"] == 2
    # LLM prompt contains staged diff
    prompt = llm.complete.call_args.kwargs["messages"][0]["content"]
    assert "diff --git" in prompt
    # Event logged
    event = await store.session.execute(select(Event).where(Event.event_type == "draft_commit"))
    assert event.scalar_one_or_none() is not None


@patch("ev.tools.draft_tools.LLMClient")
@patch("ev.tools.draft_tools.subprocess.run")
async def test_draft_pr_from_branch_diff(mock_run, mock_llm, store):
    mock_run.return_value = MagicMock(stdout="diff --git a/y.py b/y.py\n+def new_feature(): pass", stderr="", returncode=0)
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Title: Add new feature\n\nBody: This PR adds...")
    mock_llm.return_value = llm

    await store.get_or_create_project("RoboCAD", repo_path="/repos/RoboCAD")
    tool = DraftPrTool()
    tool.bind_store(store)
    result = await tool.run(project="RoboCAD")

    assert "Add new feature" in result["draft"]
    assert result["tier"] == 2


@patch("ev.tools.draft_tools.LLMClient")
async def test_draft_reply(mock_llm):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Thanks for reaching out. Let's sync next week.")
    mock_llm.return_value = llm

    tool = DraftReplyTool()
    result = await tool.run(to="recruiter@example.com", subject="Opportunity", thread_snippet="We have a role...")

    assert "Thanks for reaching out" in result["draft"]
    assert result["tier"] == 2
    prompt = llm.complete.call_args.kwargs["messages"][0]["content"]
    assert "recruiter@example.com" in prompt
    assert "We have a role" in prompt
