"""Sync personal Gmail + Google Calendar data into EV memory.

Run manually or on a schedule. Requires:
  - EV_GOOGLE_ENABLED=true
  - EV_GOOGLE_CREDENTIALS_PATH pointing to credentials.json
  - secrets/token.json from a completed OAuth flow
"""

import asyncio

from ev.config import get_settings
from ev.db.base import Base, SessionLocal, engine
from ev.ingestion.calendar import CalendarIngestion
from ev.ingestion.gmail import GmailIngestion
from ev.memory.store import MemoryStore


async def main():
    settings = get_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        store = MemoryStore(session)
        projects = await store.list_active_projects()
        project_tags = [p.name for p in projects]

        # Gmail
        gmail = GmailIngestion(settings, project_tags=project_tags)
        gmail_records, gmail_people = await gmail.ingest()
        ingested_gmail = await store.upsert_ingest(gmail_records)
        ingested_gmail_people = await store.upsert_people(gmail_people)
        print(f"Ingested {ingested_gmail} Gmail messages and {ingested_gmail_people} people")

        # Calendar
        calendar = CalendarIngestion(settings, project_tags=project_tags)
        calendar_records, deadlines, calendar_people, obligations = await calendar.ingest()
        ingested_calendar = await store.upsert_ingest(calendar_records)
        ingested_deadlines = await store.upsert_deadlines(deadlines)
        ingested_calendar_people = await store.upsert_people(calendar_people)
        ingested_obligations = await store.upsert_obligations(obligations)
        print(
            f"Ingested {ingested_calendar} calendar events, {ingested_deadlines} deadlines, "
            f"{ingested_calendar_people} people, {ingested_obligations} obligations"
        )

    print("Google sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
