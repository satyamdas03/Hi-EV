"""Seed local memory with live GitHub + notes data for demo/integration.

Usage:
    EV_RUN_INTEGRATION=1 python scripts/seed_demo.py
"""

import asyncio

from ev.config import get_settings
from ev.db.base import Base, SessionLocal, engine
from ev.ingestion.github import GitHubIngestion
from ev.ingestion.notes import NotesIngestion
from ev.memory.store import MemoryStore


async def main() -> None:
    settings = get_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)

        gh = GitHubIngestion(settings)
        repos = [("satyamdas03", "RoboCAD"), ("satyamdas03", "LearningRobotics"), ("satyamdas03", "Hi-EV")]
        for owner, name in repos:
            await store.get_or_create_project(name, repo_url=f"https://github.com/{owner}/{name}")
            gh.add_repo(owner, name)
        gh_records = await gh.ingest()
        await store.upsert_ingest(gh_records)

        notes = NotesIngestion(settings)
        note_records = await notes.ingest()
        await store.upsert_ingest(note_records)

        print(f"Seeded {len(gh_records)} GitHub records and {len(note_records)} note records")


if __name__ == "__main__":
    asyncio.run(main())
