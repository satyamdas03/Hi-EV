"""Background ingestion scheduler for the Hi-EV daemon.

Runs ingestion sources on a configurable interval, chunks long-form content,
and indexes vectors so the user's semantic memory stays up to date.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from ev.config import Settings
from ev.db.base import SessionLocal
from ev.ingestion.github import GitHubIngestion
from ev.ingestion.notes import NotesIngestion
from ev.memory.chunks import chunk_ingest_records
from ev.memory.store import MemoryStore

logger = logging.getLogger(__name__)


async def _ingest_loop(settings: Settings) -> None:
    """Background loop that periodically ingests and indexes personal data."""
    while True:
        try:
            await asyncio.sleep(settings.ingest_interval_sec)
        except asyncio.CancelledError:
            break

        if settings.kill_switch:
            logger.info("Ingestion loop skipped: kill switch enabled")
            continue
        if _in_quiet_hours(settings.quiet_start, settings.quiet_end):
            logger.info("Ingestion loop skipped: quiet hours")
            continue

        try:
            await _run_ingestion_pass(settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ingestion pass failed: %s", exc)


async def _run_ingestion_pass(settings: Settings) -> dict[str, int]:
    """Run all enabled ingestion sources once and index chunks."""
    counts: dict[str, int] = {}

    async with SessionLocal() as session:
        store = MemoryStore(session)

        # Notes ingestion is always attempted if the path exists.
        try:
            notes_source = NotesIngestion(settings)
            notes_records = await notes_source.ingest()
            counts["notes_ingest"] = await store.upsert_ingest(notes_records)
            await store.upsert_document_chunks(chunk_ingest_records(notes_records))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Notes ingestion failed: %s", exc)

        # GitHub ingestion for configured personal repos.
        if settings.github_token and settings.github_repos:
            try:
                github_source = GitHubIngestion(settings)
                for repo in settings.github_repos:
                    parts = repo.split("/")
                    if len(parts) == 2:
                        github_source.add_repo(parts[0], parts[1])
                github_records = await github_source.ingest()
                counts["github_ingest"] = await store.upsert_ingest(github_records)
                await store.upsert_document_chunks(chunk_ingest_records(github_records))
            except Exception as exc:  # noqa: BLE001
                logger.warning("GitHub ingestion failed: %s", exc)

        # Google ingestion only when OAuth is configured.
        if settings.google_enabled:
            try:
                from ev.ingestion.calendar import CalendarIngestion
                from ev.ingestion.gmail import GmailIngestion

                calendar_source = CalendarIngestion(settings)
                cal_records, deadlines, people, obligations = await calendar_source.ingest()
                counts["calendar_ingest"] = await store.upsert_ingest(cal_records)
                await store.upsert_deadlines(deadlines)
                await store.upsert_people(people)
                await store.upsert_obligations(obligations)
                await store.upsert_document_chunks(chunk_ingest_records(cal_records))

                gmail_source = GmailIngestion(settings)
                gmail_records, gmail_people = await gmail_source.ingest()
                counts["gmail_ingest"] = await store.upsert_ingest(gmail_records)
                await store.upsert_people(gmail_people)
                await store.upsert_document_chunks(chunk_ingest_records(gmail_records))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google ingestion failed: %s", exc)

    logger.info("Ingestion pass complete: %s", counts)
    return counts


def _in_quiet_hours(start: str, end: str) -> bool:
    """Return True if the current UTC time falls within quiet hours."""
    now = datetime.now(UTC).time()
    start_t = datetime.strptime(start, "%H:%M").time()  # noqa: DTZ007
    end_t = datetime.strptime(end, "%H:%M").time()  # noqa: DTZ007
    if start_t < end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t
