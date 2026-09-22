"""Structured memory store for ingested personal data."""

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, or_, select, tuple_

from ev.db.models import (
    ChatThread,
    ChatTurn,
    Deadline,
    Decision,
    DocumentChunk,
    Event,
    Ingest,
    Obligation,
    Person,
    Project,
)


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

    # ------------------------------------------------------------------
    # Semantic memory (DocumentChunk + sqlite-vec)
    # ------------------------------------------------------------------

    async def upsert_document_chunks(self, chunks: list[dict]) -> list[int]:
        """Bulk upsert DocumentChunk rows by (source, source_id, chunk_index) and index vectors.

        Returns the list of chunk ids that were inserted or updated.
        """
        if not chunks:
            return []

        # Validate and normalize keys.
        keys = set()
        for chunk in chunks:
            source = chunk.get("source", "").strip()
            source_id = chunk.get("source_id", "").strip()
            chunk_index = int(chunk.get("chunk_index", 0))
            if not source or not source_id:
                continue
            keys.add((source, source_id, chunk_index))

        if not keys:
            return []

        result = await self.session.execute(
            select(DocumentChunk).where(
                tuple_(DocumentChunk.source, DocumentChunk.source_id, DocumentChunk.chunk_index).in_(list(keys))
            )
        )
        existing = {
            (row.source, row.source_id, row.chunk_index): row
            for row in result.scalars().all()
        }

        now = datetime.now(UTC)
        new_rows: list[DocumentChunk] = []
        changed_rows: list[DocumentChunk] = []
        all_touched_ids: list[int | None] = []

        for chunk in chunks:
            source = chunk.get("source", "").strip()
            source_id = chunk.get("source_id", "").strip()
            chunk_index = int(chunk.get("chunk_index", 0))
            if not source or not source_id:
                continue
            text = (chunk.get("text") or "").strip()
            if not text:
                continue
            key = (source, source_id, chunk_index)
            row = existing.get(key)
            trusted = chunk.get("trusted", True)
            if row is None:
                new_rows.append(
                    DocumentChunk(
                        source=source,
                        source_id=source_id,
                        chunk_index=chunk_index,
                        text=text,
                        project_name=chunk.get("project_name"),
                        trusted=trusted,
                    )
                )
                all_touched_ids.append(None)
            elif row.text != text:
                row.text = text
                row.project_name = chunk.get("project_name", row.project_name)
                row.trusted = trusted
                row.updated_at = now
                changed_rows.append(row)
                self.session.add(row)
                all_touched_ids.append(row.id)
            else:
                all_touched_ids.append(row.id)

        self.session.add_all(new_rows)
        await self.session.flush()

        # Map placeholder None ids to real ids for new rows.
        real_ids = []
        new_iter = iter(new_rows)
        for stored_id in all_touched_ids:
            if stored_id is None:
                new_row = next(new_iter)
                real_ids.append(new_row.id)
            else:
                real_ids.append(stored_id)

        to_embed = [row for row in (*new_rows, *changed_rows) if row.text]
        await self._index_chunk_vectors(to_embed)

        await self.session.commit()
        return [rid for rid in real_ids if rid is not None]

    async def _index_chunk_vectors(self, rows: list[DocumentChunk]) -> None:
        """Compute embeddings and insert vector table entries.

        Existing vectors for the same chunk ids are removed first because
        sqlite-vec virtual tables can be finicky about INSERT OR REPLACE.
        """
        if not rows:
            return

        from ev.db import vector
        from ev.embeddings import get_embedding_model

        valid_rows = [row for row in rows if row.id is not None]
        if not valid_rows:
            return

        texts = [row.text for row in valid_rows]
        embeddings = get_embedding_model().encode(texts)

        vector_payloads = [
            {"id": row.id, "embedding": embedding}
            for row, embedding in zip(valid_rows, embeddings, strict=True)
        ]
        chunk_ids = [row.id for row in valid_rows]
        # Ensure vector table exists (idempotent).
        await vector.create_vector_table(self.session)
        await vector.delete_vector_chunks(self.session, chunk_ids)
        await vector.index_chunks(self.session, vector_payloads)

    async def search_document_chunks(
        self,
        query: str,
        project_name: str | None = None,
        k: int = 5,
        include_recent: int = 3,
    ) -> list[dict]:
        """Hybrid search over DocumentChunk rows.

        Combines sqlite-vec KNN, SQL keyword overlap, and recency. Returns at
        most *k* ranked results.
        """
        from ev.db import vector
        from ev.embeddings import get_embedding_model

        if not query or not query.strip():
            return []

        query_text = query.strip()
        query_embedding = get_embedding_model().encode_one(query_text)

        # Ensure vector table exists.
        await vector.create_vector_table(self.session)

        vector_results = await vector.search_chunks(self.session, query_embedding, k=k * 2)
        vector_chunk_ids = {chunk_id for chunk_id, _ in vector_results}

        # Keyword matches for hybrid recall.
        keyword_chunk_ids: set[int] = set()
        query_tokens = self._tokenize(query_text)
        if query_tokens:
            like_patterns = [f"%{token}%" for token in query_tokens]
            stmt = select(DocumentChunk)
            if project_name is not None:
                stmt = stmt.where(DocumentChunk.project_name == project_name.lower())
            # OR across tokens using SQLAlchemy's or_ helper.
            stmt = stmt.where(or_(*[DocumentChunk.text.ilike(pattern) for pattern in like_patterns]))
            stmt = stmt.limit(k * 4)
            result = await self.session.execute(stmt)
            keyword_chunk_ids = {row.id for row in result.scalars().all()}

        all_ids = vector_chunk_ids | keyword_chunk_ids
        if not all_ids:
            return []

        stmt = select(DocumentChunk).where(DocumentChunk.id.in_(list(all_ids)))
        if project_name is not None:
            stmt = stmt.where(DocumentChunk.project_name == project_name.lower())
        result = await self.session.execute(stmt)
        rows = {row.id: row for row in result.scalars().all()}

        # Also pull a few recent chunks as fallback/refresh signal.
        recent_stmt = select(DocumentChunk).order_by(desc(DocumentChunk.updated_at)).limit(include_recent)
        if project_name is not None:
            recent_stmt = recent_stmt.where(DocumentChunk.project_name == project_name.lower())
        recent_result = await self.session.execute(recent_stmt)
        for row in recent_result.scalars().all():
            if row.id not in rows:
                rows[row.id] = row

        vector_distances = {chunk_id: distance for chunk_id, distance in vector_results}
        scored: list[tuple[float, DocumentChunk]] = []
        for row in rows.values():
            score = self._chunk_score(row, query_tokens, vector_distances)
            scored.append((score, row))

        scored.sort(key=lambda item: (-item[0], item[1].updated_at or datetime.min.replace(tzinfo=UTC)))

        return [
            {
                "id": row.id,
                "source": row.source,
                "source_id": row.source_id,
                "chunk_index": row.chunk_index,
                "text": row.text,
                "project_name": row.project_name,
                "trusted": row.trusted,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "score": round(score, 4),
            }
            for score, row in scored[:k]
        ]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Normalize and tokenize query for keyword matching."""
        return {token.lower() for token in re.findall(r"[A-Za-z0-9]+", text) if len(token) > 2}

    def _chunk_score(
        self,
        row: DocumentChunk,
        query_tokens: set[str],
        vector_distances: dict[int, float],
    ) -> float:
        """Blend vector distance, keyword overlap, recency, and source trust."""
        now = datetime.now(UTC)

        # Vector distance: lower distance = higher score.
        distance = vector_distances.get(row.id, 1.0)
        vector_score = max(0.0, 1.0 - distance)

        # Keyword overlap.
        row_tokens = self._tokenize(row.text or "")
        keyword_hits = len(query_tokens & row_tokens)
        keyword_score = min(keyword_hits, 3) * 0.15

        # Recency decay: full score within 24h, half at ~1 week, etc.
        updated_at = row.updated_at
        if updated_at is None:
            recency_score = 0.0
        else:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            hours = max(0.0, (now - updated_at).total_seconds() / 3600.0)
            recency_score = 0.1 * (0.5 ** (hours / 24.0))

        # Slight boost for user-authored memory and personal notes.
        source_bonus = 0.05 if row.source in {"user_memory", "notes"} else 0.0

        # Down-weight untrusted external sources so the guard's caution signal
        # is reflected in retrieval ranking.
        trust_penalty = 0.0 if row.trusted else 0.1

        return vector_score + keyword_score + recency_score + source_bonus - trust_penalty

    async def delete_document_chunks(self, source: str, source_id: str | None = None) -> int:
        """Delete DocumentChunk rows (and their vectors) by source or source+source_id."""
        from ev.db import vector

        stmt = select(DocumentChunk).where(DocumentChunk.source == source)
        if source_id is not None:
            stmt = stmt.where(DocumentChunk.source_id == source_id)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return 0

        chunk_ids = [row.id for row in rows if row.id is not None]
        await vector.create_vector_table(self.session)
        await vector.delete_vector_chunks(self.session, chunk_ids)

        for row in rows:
            await self.session.delete(row)

        await self.session.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # Persistent chat threads
    # ------------------------------------------------------------------

    async def create_chat_thread(self, title: str | None = None) -> ChatThread:
        thread = ChatThread(title=title)
        self.session.add(thread)
        await self.session.commit()
        return thread

    async def get_chat_thread(self, thread_id) -> ChatThread | None:
        from uuid import UUID

        if isinstance(thread_id, str):
            thread_id = UUID(thread_id)
        result = await self.session.execute(select(ChatThread).where(ChatThread.id == thread_id))
        return result.scalar_one_or_none()

    async def list_chat_threads(self, limit: int = 50) -> list[ChatThread]:
        result = await self.session.execute(
            select(ChatThread).order_by(desc(ChatThread.updated_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def list_chat_turns(self, thread_id, limit: int = 100) -> list[ChatTurn]:
        from uuid import UUID

        if isinstance(thread_id, str):
            thread_id = UUID(thread_id)
        result = await self.session.execute(
            select(ChatTurn)
            .where(ChatTurn.thread_id == thread_id)
            .order_by(ChatTurn.ordinal)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_chat_turn(
        self,
        thread_id,
        role: str,
        content: str,
        tool_name: str | None = None,
        route: str | None = None,
    ) -> ChatTurn:
        from uuid import UUID

        if isinstance(thread_id, str):
            thread_id = UUID(thread_id)
        result = await self.session.execute(
            select(func.count())
            .select_from(ChatTurn)
            .where(ChatTurn.thread_id == thread_id)
        )
        ordinal = result.scalar_one() or 0
        turn = ChatTurn(
            thread_id=thread_id,
            ordinal=ordinal,
            role=role,
            content=content,
            tool_name=tool_name,
            route=route,
        )
        self.session.add(turn)
        # Touch the parent thread's updated_at timestamp.
        thread = await self.get_chat_thread(thread_id)
        if thread:
            thread.updated_at = datetime.now(UTC)
            self.session.add(thread)
        await self.session.commit()
        return turn

    async def delete_chat_thread(self, thread_id) -> bool:
        from uuid import UUID

        if isinstance(thread_id, str):
            thread_id = UUID(thread_id)
        thread = await self.get_chat_thread(thread_id)
        if not thread:
            return False
        await self.session.delete(thread)
        await self.session.commit()
        return True
