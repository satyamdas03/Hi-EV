"""Hi-EV SQLAlchemy ORM models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)

from .base import Base


def now_utc() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(UTC)


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
