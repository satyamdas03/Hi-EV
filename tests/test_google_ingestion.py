"""Tests for read-only Gmail + Calendar ingestion."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from ev.config import Settings
from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Deadline
from ev.memory.store import MemoryStore
from ev.security.boundary import PersonalOnlyError


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _gmail_service():
    service = MagicMock()
    list_resp = MagicMock()
    list_resp.execute.return_value = {"messages": [{"id": "m1", "threadId": "t1"}]}
    service.users.return_value.messages.return_value.list.return_value = list_resp

    get_resp = MagicMock()
    get_resp.execute.return_value = {
        "id": "m1",
        "threadId": "t1",
        "snippet": "Let's catch up next week.",
        "payload": {
            "headers": [
                {"name": "From", "value": "friend@example.com"},
                {"name": "Subject", "value": "Catch up"},
                {"name": "Date", "value": "Mon, 15 Sep 2026 10:00:00 GMT"},
            ]
        },
    }
    service.users.return_value.messages.return_value.get.return_value = get_resp
    return service


def _calendar_service():
    service = MagicMock()
    list_resp = MagicMock()
    list_resp.execute.return_value = {
        "items": [
            {
                "id": "e1",
                "summary": "Patent filing due",
                "description": "Complete spec",
                "start": {"dateTime": "2026-09-20T10:00:00Z"},
                "end": {"dateTime": "2026-09-20T11:00:00Z"},
            }
        ]
    }
    service.events.return_value.list.return_value = list_resp
    return service


async def test_gmail_ingestion_personal_only(store):
    from ev.ingestion.gmail import GmailIngestion
    with pytest.raises(PersonalOnlyError):
        GmailIngestion(Settings(personal_only=False, google_enabled=True), service=MagicMock())


async def test_gmail_ingestion_disabled(store):
    from ev.ingestion.gmail import GmailIngestion
    with pytest.raises(RuntimeError):
        GmailIngestion(Settings(personal_only=True, google_enabled=False), service=MagicMock())


async def test_gmail_ingestion_reads_and_never_writes():
    from ev.ingestion.gmail import GmailIngestion
    service = _gmail_service()
    ingester = GmailIngestion(Settings(personal_only=True, google_enabled=True), service=service)
    records, people = await ingester.ingest()
    assert len(records) == 1
    assert records[0]["source"] == "gmail_messages"
    assert records[0]["source_id"] == "m1"
    assert records[0]["content_hash"]
    assert records[0]["privacy_level"] == "sensitive"
    assert "Catch up" in records[0]["content"]

    assert len(people) == 1
    assert people[0]["email"] == "friend@example.com"

    # No destructive or send calls
    assert not service.users.return_value.messages.return_value.send.called
    assert not service.users.return_value.messages.return_value.delete.called
    assert not service.users.return_value.messages.return_value.trash.called


async def test_gmail_ingestion_skips_work_senders():
    from ev.ingestion.gmail import GmailIngestion
    service = _gmail_service()
    response = service.users.return_value.messages.return_value.get.return_value
    response.execute.return_value["payload"]["headers"][0]["value"] = "boss@financialsimplicity.com"
    ingester = GmailIngestion(Settings(personal_only=True, google_enabled=True), service=service)
    records, people = await ingester.ingest()
    assert records == []
    assert people == []


async def test_gmail_ingestion_uses_project_tags():
    from ev.ingestion.gmail import GmailIngestion
    service = _gmail_service()
    response = service.users.return_value.messages.return_value.get.return_value
    response.execute.return_value["payload"]["headers"][1]["value"] = "RoboCAD actuator review"
    ingester = GmailIngestion(
        Settings(personal_only=True, google_enabled=True),
        service=service,
        project_tags=["RoboCAD", "Hi-EV"],
    )
    records, _people = await ingester.ingest()
    assert records[0]["project_tag"] == "robocad"


async def test_calendar_ingestion_personal_only(store):
    from ev.ingestion.calendar import CalendarIngestion
    with pytest.raises(PersonalOnlyError):
        CalendarIngestion(Settings(personal_only=False, google_enabled=True), service=MagicMock())


async def test_calendar_ingestion_disabled(store):
    from ev.ingestion.calendar import CalendarIngestion
    with pytest.raises(RuntimeError):
        CalendarIngestion(Settings(personal_only=True, google_enabled=False), service=MagicMock())


async def test_calendar_ingestion_extracts_events_and_deadlines():
    from ev.ingestion.calendar import CalendarIngestion
    service = _calendar_service()
    ingester = CalendarIngestion(Settings(personal_only=True, google_enabled=True), service=service)
    records, deadlines, people, obligations = await ingester.ingest()
    assert len(records) == 1
    assert records[0]["source"] == "calendar_events"
    assert records[0]["source_id"] == "e1"
    assert records[0]["content_hash"]
    assert "Patent filing due" in records[0]["content"]

    assert len(deadlines) == 1
    assert deadlines[0]["title"] == "Patent filing due"
    assert deadlines[0]["source"] == "calendar"
    assert deadlines[0]["source_id"] == "e1"

    assert len(people) == 0
    assert len(obligations) == 0  # "Patent" is deadline-like, not obligation-like

    # No create/update/delete calls
    assert not service.events.return_value.insert.called
    assert not service.events.return_value.update.called
    assert not service.events.return_value.delete.called


async def test_store_upsert_deadlines(store):
    await store.upsert_deadlines([
        {"title": "A", "due_date": "2026-09-20T10:00:00+00:00", "source": "calendar", "source_id": "e1", "priority": "high"},
        {"title": "B", "due_date": "2026-09-21T10:00:00+00:00", "source": "calendar", "source_id": "e2", "priority": "medium"},
    ])
    result = await store.session.execute(select(Deadline))
    rows = result.scalars().all()
    assert len(rows) == 2
    assert {r.title for r in rows} == {"A", "B"}

    # Idempotent
    await store.upsert_deadlines([
        {"title": "A updated", "due_date": "2026-09-20T10:00:00+00:00", "source": "calendar", "source_id": "e1", "priority": "high"},
    ])
    result = await store.session.execute(select(Deadline).where(Deadline.source_id == "e1"))
    row = result.scalar_one()
    assert row.title == "A updated"
