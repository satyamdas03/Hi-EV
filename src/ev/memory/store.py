"""Structured memory store for ingested personal data."""

from datetime import UTC, datetime

from sqlalchemy import desc, func, select, tuple_

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
            select(Ingest).where(tuple_(Ingest.source, Ingest.source_id).in_(list(keys)))
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

    async def list_active_projects(self) -> list[Project]:
        result = await self.session.execute(select(Project).where(Project.active == True))
        return list(result.scalars().all())

    async def _count_open_source(self, source: str, project_name: str) -> int:
        tag = project_name.lower()
        result = await self.session.execute(
            select(func.count())
            .select_from(Ingest)
            .where(
                Ingest.source == source,
                Ingest.project_tag == tag,
                Ingest.content.ilike("%state: open%"),
            )
        )
        return result.scalar_one() or 0

    async def count_open_issues(self, project_name: str) -> int:
        return await self._count_open_source("github_issues", project_name)

    async def count_open_prs(self, project_name: str) -> int:
        return await self._count_open_source("github_prs", project_name)

    async def recent_notes(self, project_name: str, limit: int = 5) -> list[Ingest]:
        tag = project_name.lower()
        result = await self.session.execute(
            select(Ingest)
            .where(Ingest.source == "notes", Ingest.project_tag == tag)
            .order_by(desc(Ingest.updated_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_event(self, project_name: str, event_type: str, description: str, source_url: str | None = None) -> Event:
        project = await self.get_or_create_project(project_name)
        event = Event(project_id=project.id, event_type=event_type, description=description, source_url=source_url)
        self.session.add(event)
        await self.session.commit()
        return event
