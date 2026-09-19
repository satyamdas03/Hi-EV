"""Hi-EV SQLAlchemy ORM models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)

from .base import Base


def now_utc() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(UTC)


class DocumentChunk(Base):
    """Chunked document metadata for semantic memory.

    The actual vector for each chunk lives in the sqlite-vec / pgvector
    virtual table `vec_document_chunks`, keyed by this integer id.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source", "source_id", "chunk_index",
            name="uix_document_chunk_source",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=False)
    project_name = Column(String(128), nullable=True, index=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    trusted = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Ingest(Base):
    """Raw ingestion records with idempotency via (source, source_id)."""

    __tablename__ = "ingest"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uix_ingest_source_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=True)
    project_tag = Column(String(128), nullable=True, index=True)
    privacy_level = Column(String(32), default="personal")
    trusted = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Project(Base):
    """Structured project memory."""

    __tablename__ = "projects"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False, unique=True, index=True)
    repo_url = Column(String(512), nullable=True)
    goal = Column(Text, nullable=True)
    current_phase = Column(String(128), nullable=True)
    status = Column(String(32), default="active")
    active = Column(Boolean, default=True)
    repo_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Event(Base):
    """Episodic log of things that happened."""

    __tablename__ = "events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    event_type = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=False)
    source_url = Column(String(1024), nullable=True)
    happened_at = Column(DateTime(timezone=True), default=now_utc)


class Deadline(Base):
    """Structured deadlines extracted from calendar and explicit captures."""

    __tablename__ = "deadlines"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uix_deadline_source_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(512), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    priority = Column(String(32), default="medium")
    status = Column(String(32), default="open")
    snooze_until = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=False)
    project_name = Column(String(128), nullable=True, index=True)
    last_reminded = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Person(Base):
    """People EV learns about from Gmail, Calendar, and manual captures."""

    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("email", name="uix_person_email"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(256), nullable=False, unique=True, index=True)
    name = Column(String(256), nullable=True)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    last_contact_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Obligation(Base):
    """Things owed or expected between people/projects."""

    __tablename__ = "obligations"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uix_obligation_source_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="open")
    snooze_until = Column(DateTime(timezone=True), nullable=True)
    project_name = Column(String(128), nullable=True, index=True)
    owed_by_person_id = Column(
        Uuid(as_uuid=True), ForeignKey("people.id"), nullable=True
    )
    owed_to_person_id = Column(
        Uuid(as_uuid=True), ForeignKey("people.id"), nullable=True
    )
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Decision(Base):
    """Recorded decisions with rationale."""

    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uix_decision_source_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String(512), nullable=False)
    decision_text = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    made_at = Column(DateTime(timezone=True), default=now_utc)
    project_name = Column(String(128), nullable=True, index=True)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
