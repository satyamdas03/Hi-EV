"""Structured memory store for ingested personal data."""

from datetime import UTC, datetime

from sqlalchemy import select

from ev.db.models import Event, Ingest, Project


class MemoryStore:
    """CRUD and aggregation layer over the Hi-EV memory tables."""

    def __init__(self, session):
        self.session = session

    async def upsert_ingest(self, records: list[dict]) -> int:
        """Bulk upsert Ingest rows by (source, source_id).

        Uses a portable query-and-merge strategy so the operation is idempotent
        on both Postgres (the production target) and the SQLite+aiosqlite test
        fallback used when no local Postgres server is running.
        """
        if not records:
            return 0

        keys = {(r["source"], r["source_id"]) for r in records}
        result = await self.session.execute(
            select(Ingest).where(
                Ingest.source.in_([s for s, _ in keys])
                & Ingest.source_id.in_([i for _, i in keys])
            )
        )
        existing = {(row.source, row.source_id): row for row in result.scalars().all()}

        new_rows: list[Ingest] = []
        now = datetime.now(UTC)
        for record in records:
            key = (record["source"], record["source_id"])
            row = existing.get(key)
            if row is None:
                new_rows.append(Ingest(**record))
            else:
                row.content_hash = record.get("content_hash", row.content_hash)
                row.content = record.get("content", row.content)
                row.updated_at = now
                self.session.add(row)

        self.session.add_all(new_rows)
        await self.session.commit()
        return len(records)

    async def count_ingest_by_source(self, source: str) -> int:
        result = await self.session.execute(select(Ingest).where(Ingest.source == source))
        return len(result.scalars().all())

    async def get_or_create_project(self, name: str, **kwargs) -> Project:
        result = await self.session.execute(select(Project).where(Project.name == name))
        project = result.scalar_one_or_none()
        if project is None:
            project = Project(name=name, **kwargs)
            self.session.add(project)
            await self.session.commit()
        return project

    async def add_event(self, project_name: str, event_type: str, description: str, source_url: str | None = None) -> Event:
        project = await self.get_or_create_project(project_name)
        event = Event(project_id=project.id, event_type=event_type, description=description, source_url=source_url)
        self.session.add(event)
        await self.session.commit()
        return event
