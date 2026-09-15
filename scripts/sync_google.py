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

        # Gmail
        gmail = GmailIngestion(settings)
        gmail_records = await gmail.ingest()
        ingested_gmail = await store.upsert_ingest(gmail_records)
        print(f"Ingested {ingested_gmail} Gmail messages")

        # Calendar
        calendar = CalendarIngestion(settings)
        calendar_records, deadlines = await calendar.ingest()
        ingested_calendar = await store.upsert_ingest(calendar_records)
        ingested_deadlines = await store.upsert_deadlines(deadlines)
        print(f"Ingested {ingested_calendar} calendar events and {ingested_deadlines} deadlines")

    print("Google sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
