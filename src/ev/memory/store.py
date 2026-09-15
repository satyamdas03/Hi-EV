"""Structured memory store for ingested personal data."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select, tuple_

from ev.db.models import Deadline, Decision, Event, Ingest, Obligation, Person, Project


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

    @staticmethod
    def _parse_due_date(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise TypeError(f"Unsupported due_date type: {type(value)}")

    async def upsert_deadlines(self, deadlines: list[dict]) -> int:
        """Bulk upsert Deadline rows by (source, source_id)."""
        if not deadlines:
            return 0
        keys = {(d["source"], d["source_id"]) for d in deadlines}
        result = await self.session.execute(
            select(Deadline).where(tuple_(Deadline.source, Deadline.source_id).in_(list(keys)))
        )
        existing = {(row.source, row.source_id): row for row in result.scalars().all()}

        new_rows: list[Deadline] = []
        now = datetime.now(UTC)
        for data in deadlines:
            key = (data["source"], data["source_id"])
            deadline_data = dict(data)
            deadline_data["due_date"] = self._parse_due_date(deadline_data.get("due_date"))
            row = existing.get(key)
            if row is None:
                new_rows.append(Deadline(**deadline_data))
            else:
                row.title = deadline_data.get("title", row.title)
                row.due_date = deadline_data.get("due_date", row.due_date)
                row.priority = deadline_data.get("priority", row.priority)
                row.project_name = deadline_data.get("project_name", row.project_name)
                row.updated_at = now
                self.session.add(row)
        self.session.add_all(new_rows)
        await self.session.commit()
        return len(deadlines)

    async def get_upcoming_deadlines(
        self,
        after: datetime | None = None,
        before: datetime | None = None,
        status: str | None = "open",
    ) -> list[Deadline]:
        stmt = select(Deadline)
        if status is not None:
            stmt = stmt.where(Deadline.status == status)
        if after is not None:
            stmt = stmt.where(Deadline.due_date >= after)
        if before is not None:
            stmt = stmt.where(Deadline.due_date <= before)
        stmt = stmt.order_by(Deadline.due_date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_urgent_deadlines(self, hours: int = 72) -> int:
        now = datetime.now(UTC)
        horizon = now + timedelta(hours=hours)
        result = await self.session.execute(
            select(func.count())
            .select_from(Deadline)
            .where(
                Deadline.status == "open",
                Deadline.due_date <= horizon,
                ((Deadline.snooze_until.is_(None)) | (Deadline.snooze_until <= now)),
            )
        )
        return result.scalar_one() or 0

    async def mark_deadline_reminded(self, deadline_id) -> None:
        result = await self.session.execute(select(Deadline).where(Deadline.id == deadline_id))
        row = result.scalar_one_or_none()
        if row:
            row.last_reminded = datetime.now(UTC)
            self.session.add(row)
            await self.session.commit()

    async def snooze_deadline(self, deadline_id, until: datetime) -> None:
        result = await self.session.execute(select(Deadline).where(Deadline.id == deadline_id))
        row = result.scalar_one_or_none()
        if row:
            row.snooze_until = until
            row.status = "snoozed"
            self.session.add(row)
            await self.session.commit()

    async def upsert_people(self, people: list[dict]) -> int:
        """Bulk upsert Person rows by email."""
        if not people:
            return 0
        # Deduplicate by email within the batch to avoid UNIQUE constraint errors.
        seen = {}
        for p in people:
            email = p["email"]
            if email not in seen or p.get("last_contact_at") and (
                not seen[email].get("last_contact_at")
                or self._parse_due_date(p["last_contact_at"]) > self._parse_due_date(seen[email]["last_contact_at"])
            ):
                seen[email] = p
        deduped = list(seen.values())

        emails = {p["email"] for p in deduped}
        result = await self.session.execute(select(Person).where(Person.email.in_(list(emails))))
        existing = {row.email: row for row in result.scalars().all()}

        new_rows: list[Person] = []
        now = datetime.now(UTC)
        for data in deduped:
            email = data["email"]
            row = existing.get(email)
            parsed_data = dict(data)
            parsed_data["last_contact_at"] = self._parse_due_date(parsed_data.get("last_contact_at"))
            if row is None:
                new_rows.append(Person(**parsed_data))
            else:
                if data.get("name"):
                    row.name = data["name"]
                if data.get("source"):
                    row.source = data["source"]
                if data.get("source_id"):
                    row.source_id = data["source_id"]
                if data.get("notes"):
                    row.notes = data["notes"]
                if parsed_data.get("last_contact_at"):
                    row.last_contact_at = parsed_data["last_contact_at"]
                row.updated_at = now
                self.session.add(row)
        self.session.add_all(new_rows)
        await self.session.commit()
        return len(deduped)

    async def list_people(self, project_name: str | None = None, limit: int = 100) -> list[Person]:
        stmt = select(Person)
        if project_name is not None:
            stmt = stmt.where(Person.source.ilike(f"%{project_name.lower()}%"))
        stmt = stmt.order_by(desc(Person.last_contact_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_obligations(self, obligations: list[dict]) -> int:
        """Bulk upsert Obligation rows by (source, source_id)."""
        if not obligations:
            return 0
        keys = {(o["source"], o["source_id"]) for o in obligations}
        result = await self.session.execute(
            select(Obligation).where(tuple_(Obligation.source, Obligation.source_id).in_(list(keys)))
        )
        existing = {(row.source, row.source_id): row for row in result.scalars().all()}

        new_rows: list[Obligation] = []
        now = datetime.now(UTC)
        for data in obligations:
            key = (data["source"], data["source_id"])
            obligation_data = dict(data)
            obligation_data["due_date"] = self._parse_due_date(obligation_data.get("due_date"))
            row = existing.get(key)
            if row is None:
                new_rows.append(Obligation(**obligation_data))
            else:
                row.title = obligation_data.get("title", row.title)
                row.description = obligation_data.get("description", row.description)
                row.due_date = obligation_data.get("due_date", row.due_date)
                row.status = obligation_data.get("status", row.status)
                row.project_name = obligation_data.get("project_name", row.project_name)
                row.updated_at = now
                self.session.add(row)
        self.session.add_all(new_rows)
        await self.session.commit()
        return len(obligations)

    async def list_obligations(
        self,
        status: str | None = None,
        project_name: str | None = None,
        overdue: bool = False,
    ) -> list[Obligation]:
        stmt = select(Obligation)
        if status is not None:
            stmt = stmt.where(Obligation.status == status)
        if project_name is not None:
            stmt = stmt.where(Obligation.project_name == project_name.lower())
        if overdue:
            stmt = stmt.where(Obligation.due_date < datetime.now(UTC))
        stmt = stmt.order_by(Obligation.due_date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_decisions(self, decisions: list[dict]) -> int:
        """Bulk upsert Decision rows by (source, source_id)."""
        if not decisions:
            return 0
        keys = {(d["source"], d["source_id"]) for d in decisions}
        result = await self.session.execute(
            select(Decision).where(tuple_(Decision.source, Decision.source_id).in_(list(keys)))
        )
        existing = {(row.source, row.source_id): row for row in result.scalars().all()}

        new_rows: list[Decision] = []
        now = datetime.now(UTC)
        for data in decisions:
            key = (data["source"], data["source_id"])
            decision_data = dict(data)
            decision_data["made_at"] = self._parse_due_date(decision_data.get("made_at")) if decision_data.get("made_at") else now
            row = existing.get(key)
            if row is None:
                new_rows.append(Decision(**decision_data))
            else:
                row.topic = decision_data.get("topic", row.topic)
                row.decision_text = decision_data.get("decision_text", row.decision_text)
                row.rationale = decision_data.get("rationale", row.rationale)
                row.made_at = decision_data.get("made_at", row.made_at)
                row.project_name = decision_data.get("project_name", row.project_name)
                row.updated_at = now
                self.session.add(row)
        self.session.add_all(new_rows)
        await self.session.commit()
        return len(decisions)

    async def list_decisions(self, project_name: str | None = None, limit: int = 20) -> list[Decision]:
        stmt = select(Decision)
        if project_name is not None:
            stmt = stmt.where(Decision.project_name == project_name.lower())
        stmt = stmt.order_by(desc(Decision.made_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_emails(self, from_email: str, days: int = 7, limit: int = 5) -> list[Ingest]:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self.session.execute(
            select(Ingest)
            .where(
                Ingest.source == "gmail_messages",
                Ingest.content.ilike(f"%from: %{from_email}%"),
                Ingest.updated_at >= since,
            )
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
