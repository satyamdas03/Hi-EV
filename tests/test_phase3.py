"""Tests for Phase 3 memory tables, tools, CLI, and API."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from sqlalchemy import select

from ev.cli.main import cli
from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Deadline
from ev.memory.store import MemoryStore
from ev.server.api import app
from ev.tools.alerts_tool import AlertsTool
from ev.tools.deadline_watcher import DeadlineWatcherTool
from ev.tools.obligations_tool import ObligationsTool
from ev.tools.people_tool import PeopleTool
from ev.tools.prep_tool import PrepTool
from ev.tools.registry import ToolRegistry


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------- Memory store: people / obligations / decisions ----------


async def test_upsert_people_idempotent(store):
    inserted = await store.upsert_people([
        {"email": "alice@example.com", "name": "Alice", "source": "gmail_messages", "source_id": "msg1"},
    ])
    assert inserted == 1
    first_count = len(await store.list_people())

    updated = await store.upsert_people([
        {"email": "alice@example.com", "name": "Alice Smith", "source": "gmail_messages", "source_id": "msg1"},
    ])
    assert updated == 1
    people = await store.list_people()
    assert len(people) == first_count == 1
    assert people[0].name == "Alice Smith"


async def test_list_people_filters_by_project_source(store):
    await store.upsert_people([
        {"email": "bob@robocad.dev", "name": "Bob", "source": "calendar_robocad", "source_id": "c1"},
        {"email": "carol@hiev.dev", "name": "Carol", "source": "calendar_hiev", "source_id": "c2"},
    ])
    robocad_people = await store.list_people(project_name="robocad")
    assert len(robocad_people) == 1
    assert robocad_people[0].email == "bob@robocad.dev"


async def test_upsert_obligations_and_overdue_filter(store):
    now = datetime.now(UTC)
    await store.upsert_obligations([
        {"title": "Pay invoice", "source": "gmail_messages", "source_id": "o1", "due_date": now - timedelta(days=1), "status": "open"},
        {"title": "Review PR", "source": "gmail_messages", "source_id": "o2", "due_date": now + timedelta(days=2), "status": "open"},
    ])
    open_all = await store.list_obligations(status="open")
    assert len(open_all) == 2
    overdue = await store.list_obligations(status="open", overdue=True)
    assert len(overdue) == 1
    assert overdue[0].title == "Pay invoice"


async def test_upsert_decisions_idempotent(store):
    made = datetime.now(UTC) - timedelta(days=1)
    await store.upsert_decisions([
        {"topic": "Use FastAPI", "decision_text": "Yes", "rationale": "async", "source": "manual", "source_id": "d1", "made_at": made, "project_name": "hiev"},
    ])
    first = await store.list_decisions()
    assert len(first) == 1

    await store.upsert_decisions([
        {"topic": "Use FastAPI", "decision_text": "Yes definitely", "rationale": "async and clean", "source": "manual", "source_id": "d1", "made_at": made, "project_name": "hiev"},
    ])
    second = await store.list_decisions()
    assert len(second) == 1
    assert second[0].decision_text == "Yes definitely"


async def test_snooze_and_mark_reminded(store):
    now = datetime.now(UTC)
    await store.upsert_deadlines([
        {"title": "Tax return", "source": "calendar", "source_id": "dl1", "due_date": now + timedelta(days=2), "status": "open"},
    ])
    dl = (await store.get_upcoming_deadlines(status="open"))[0]
    assert dl.last_reminded is None
    await store.mark_deadline_reminded(dl.id)
    refreshed = (await store.get_upcoming_deadlines(status="open"))[0]
    assert refreshed.last_reminded is not None

    await store.snooze_deadline(dl.id, now + timedelta(days=7))
    result = await store.session.execute(select(Deadline).where(Deadline.id == dl.id))
    snoozed = result.scalar_one()
    assert snoozed.status == "snoozed"
    assert snoozed.snooze_until is not None


async def test_count_urgent_deadlines_respects_snooze(store):
    now = datetime.now(UTC)
    await store.upsert_deadlines([
        {"title": "Urgent", "source": "calendar", "source_id": "u1", "due_date": now + timedelta(hours=1), "status": "open"},
        {"title": "Snoozed", "source": "calendar", "source_id": "u2", "due_date": now + timedelta(hours=1), "status": "open", "snooze_until": now + timedelta(days=1)},
    ])
    assert await store.count_urgent_deadlines(hours=72) == 1


async def test_get_recent_emails(store):
    now = datetime.now(UTC)
    await store.upsert_ingest([
        {"source": "gmail_messages", "source_id": "g1", "content_hash": "h1", "content": "from: sender@example.com\nsubject: hello", "updated_at": now - timedelta(hours=1)},
        {"source": "gmail_messages", "source_id": "g2", "content_hash": "h2", "content": "from: other@example.com\nsubject: hi", "updated_at": now - timedelta(hours=1)},
    ])
    emails = await store.get_recent_emails("sender@example.com", days=7, limit=5)
    assert len(emails) == 1


# ---------- Tools ----------


async def test_deadline_watcher_buckets(store):
    now = datetime.now(UTC)
    # Keep the "today" deadline within the current calendar day so the bucket
    # is deterministic regardless of what time the test runs.
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    today_deadline = min(now + timedelta(hours=2), today_end - timedelta(seconds=1))
    await store.upsert_deadlines([
        {"title": "Overdue", "source": "cal", "source_id": "b1", "due_date": now - timedelta(days=1), "status": "open"},
        {"title": "Today", "source": "cal", "source_id": "b2", "due_date": today_deadline, "status": "open"},
        {"title": "Week", "source": "cal", "source_id": "b3", "due_date": now + timedelta(days=3), "status": "open"},
        {"title": "Future", "source": "cal", "source_id": "b4", "due_date": now + timedelta(days=14), "status": "open"},
    ])
    watcher = DeadlineWatcherTool(urgent_hours=72)
    watcher.bind_store(store)
    result = await watcher.run()
    assert result["counts"]["overdue"] == 1
    assert result["counts"]["today"] == 1
    assert result["counts"]["this_week"] == 1
    assert result["counts"]["future"] == 1
    assert result["counts"]["urgent"] == 3  # overdue + today + week within 72h


async def test_deadline_watcher_hides_snoozed(store):
    now = datetime.now(UTC)
    await store.upsert_deadlines([
        {"title": "Snoozed", "source": "cal", "source_id": "s1", "due_date": now + timedelta(hours=2), "status": "open", "snooze_until": now + timedelta(days=1)},
    ])
    watcher = DeadlineWatcherTool(urgent_hours=72)
    watcher.bind_store(store)
    result = await watcher.run()
    assert result["counts"]["total"] == 1
    assert result["counts"]["today"] == 0


async def test_alerts_tool_digest(store):
    now = datetime.now(UTC)
    await store.upsert_deadlines([
        {"title": "Due soon", "source": "cal", "source_id": "a1", "due_date": now + timedelta(hours=2), "status": "open", "priority": "high"},
    ])
    await store.upsert_obligations([
        {"title": "Old promise", "source": "gmail", "source_id": "ao1", "due_date": now - timedelta(days=2), "status": "open"},
    ])
    alerts = AlertsTool(urgent_hours=72)
    alerts.bind_store(store)
    result = await alerts.run()
    assert "urgent deadline" in result["digest"].lower()
    assert "Due soon" in result["digest"]
    assert result["overdue_obligations"] == 1


async def test_alerts_tool_empty(store):
    alerts = AlertsTool()
    alerts.bind_store(store)
    result = await alerts.run()
    assert "no urgent deadlines" in result["digest"].lower()


async def test_people_tool(store):
    await store.upsert_people([
        {"email": "dave@example.com", "name": "Dave", "source": "calendar", "source_id": "p1"},
    ])
    registry = ToolRegistry(store)
    registry.register(PeopleTool())
    result = await registry.get("people").run()
    assert len(result["people"]) == 1
    assert result["people"][0]["email"] == "dave@example.com"


async def test_obligations_tool(store):
    now = datetime.now(UTC)
    await store.upsert_obligations([
        {"title": "Respond", "source": "gmail", "source_id": "ob1", "due_date": now - timedelta(days=1), "status": "open", "project_name": "hiev"},
    ])
    registry = ToolRegistry(store)
    registry.register(ObligationsTool())
    result = await registry.get("obligations").run(overdue=True)
    assert len(result["obligations"]) == 1


@patch("ev.tools.prep_tool.LLMClient")
async def test_prep_tool_builds_packet(mock_llm, store):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Agenda item")
    mock_llm.return_value = llm

    now = datetime.now(UTC)
    event_time = now + timedelta(hours=2)
    await store.upsert_ingest([
        {
            "source": "calendar_events",
            "source_id": "ev1",
            "content_hash": "h1",
            "content": "Event: RoboCAD standup\nAttendees: 2\nattendee@example.com",
            "updated_at": event_time,
        }
    ])
    await store.upsert_people([
        {"email": "attendee@example.com", "name": "Attendee", "source": "calendar", "source_id": "p1"},
    ])

    tool = PrepTool()
    tool.bind_store(store)
    result = await tool.run(title="RoboCAD standup", time=event_time.isoformat())
    assert result["event"]["title"] == "RoboCAD standup"
    assert any(a["email"] == "attendee@example.com" for a in result["attendees"])
    assert result["prep"] == "Agenda item"
    llm.complete.assert_awaited_once()


async def test_prep_tool_no_matching_event(store):
    tool = PrepTool()
    tool.bind_store(store)
    result = await tool.run(title="Nonexistent", time=datetime.now(UTC).isoformat())
    assert result["event"] is None
    assert "no matching calendar event" in result["prep"].lower()


# ---------- CLI ----------


@pytest.fixture
async def seeded_store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("HiEV", current_phase="Phase 3", active=True)
        now = datetime.now(UTC)
        await store.upsert_deadlines([
            {"title": "Ship Phase 3", "source": "manual", "source_id": "d1", "due_date": now + timedelta(hours=2), "status": "open", "project_name": "hiev"},
            {"title": "Old thing", "source": "manual", "source_id": "d2", "due_date": now - timedelta(days=1), "status": "open", "project_name": "hiev"},
        ])
        await store.upsert_people([
            {"email": "eva@example.com", "name": "Eva", "source": "gmail_messages", "source_id": "p1"},
        ])
        await store.upsert_obligations([
            {"title": "Invoice", "source": "gmail", "source_id": "o1", "due_date": now - timedelta(days=1), "status": "open", "project_name": "hiev"},
        ])
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_cli_deadlines(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["deadlines", "list", "--json"])
    assert result.exit_code == 0
    assert "Ship Phase 3" in result.output
    assert '"overdue"' in result.output


def test_cli_people(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["people", "list"])
    assert result.exit_code == 0
    assert "Eva" in result.output


def test_cli_obligations(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["obligations", "list", "--overdue"])
    assert result.exit_code == 0
    assert "Invoice" in result.output


def test_cli_alerts(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts"])
    assert result.exit_code == 0
    assert "urgent" in result.output.lower()


@patch("ev.tools.prep_tool.LLMClient")
def test_cli_prep_meeting(mock_llm, seeded_store):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="Prep output")
    mock_llm.return_value = llm

    runner = CliRunner()
    now = datetime.now(UTC)
    result = runner.invoke(cli, ["prep", "meeting", "Review", "--time", now.isoformat()])
    assert result.exit_code == 0
    assert "Prep output" in result.output or "no matching calendar event" in result.output


# ---------- API ----------


@pytest.fixture
def client(store):
    # TestClient uses sync context, but the DB fixture is async-only.
    # We rely on isolated test DB configured in conftest and just use TestClient directly.
    return TestClient(app)


@patch("ev.tools.prep_tool.LLMClient")
def test_api_deadlines(mock_llm, client):
    response = client.post("/deadlines", json={})
    assert response.status_code == 200
    data = response.json()
    assert "counts" in data


@patch("ev.tools.prep_tool.LLMClient")
def test_api_people(mock_llm, client):
    response = client.post("/people", json={})
    assert response.status_code == 200
    assert "people" in response.json()


@patch("ev.tools.prep_tool.LLMClient")
def test_api_obligations(mock_llm, client):
    response = client.post("/obligations", json={"status": "open", "overdue": False})
    assert response.status_code == 200
    assert "obligations" in response.json()


@patch("ev.tools.prep_tool.LLMClient")
def test_api_alerts(mock_llm, client):
    response = client.post("/alerts")
    assert response.status_code == 200
    assert "digest" in response.json()


@patch("ev.tools.prep_tool.LLMClient")
def test_api_prep(mock_llm, client):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="API prep")
    mock_llm.return_value = llm

    response = client.post("/prep", json={"title": "RoboCAD sync", "time": datetime.now(UTC).isoformat()})
    assert response.status_code == 200
    data = response.json()
    assert "prep" in data
