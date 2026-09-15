# Task 2: Database models and pgvector schema

**Files:**
- Create: `src/ev/db/base.py`
- Create: `src/ev/db/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `ev.config.get_settings().database_url`.
- Produces:
  - `ev.db.base.Base` — declarative base.
  - `ev.db.base.engine` — SQLAlchemy async engine.
  - `ev.db.base.SessionLocal` — sessionmaker.
  - `ev.db.models.Ingest` — raw ingest table.
  - `ev.db.models.Project` — structured project table.
  - `ev.db.models.Event` — episodic events table.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
import pytest
from sqlalchemy import select
from ev.db.base import Base, engine, SessionLocal
from ev.db.models import Project, Ingest, Event

@pytest.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def test_create_project(db_session):
    p = Project(name="RoboCAD", repo_url="https://github.com/satyamdas03/RoboCAD", current_phase="Phase 29")
    db_session.add(p)
    await db_session.commit()
    result = await db_session.execute(select(Project).where(Project.name == "RoboCAD"))
    assert result.scalar_one().current_phase == "Phase 29"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_create_project -v`
Expected: FAIL — `ev.db` module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/ev/db/__init__.py
from .base import Base, engine, SessionLocal
from .models import Ingest, Project, Event

__all__ = ["Base", "engine", "SessionLocal", "Ingest", "Project", "Event"]

# src/ev/db/base.py
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "postgresql+asyncpg://localhost:5432/hiev_test"

class Base(AsyncAttrs, DeclarativeBase):
    pass

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# src/ev/db/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

def now_utc():
    return datetime.now(timezone.utc)

class Ingest(Base):
    __tablename__ = "ingest"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uix_ingest_source_id"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(512), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=True)
    project_tag = Column(String(128), nullable=True, index=True)
    privacy_level = Column(String(32), default="personal")
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    event_type = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=False)
    source_url = Column(String(1024), nullable=True)
    happened_at = Column(DateTime(timezone=True), default=now_utc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py::test_create_project -v`
Expected: PASS (requires a local Postgres with `hiev_test` database).

- [ ] **Step 5: Commit**

```bash
git add src/ev/db/ alembic.ini alembic/ tests/test_db.py
git commit -m "feat: add async Postgres schema and pgvector models" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

## Important Notes

- This task requires a local Postgres database named `hiev_test` for tests. The implementer must ensure Postgres + asyncpg is available, or adjust the test fixture to use SQLite with async compatibility only if absolutely necessary. Prefer real Postgres + pgvector because pgvector columns are required later.
- The `engine` and `SessionLocal` in `src/ev/db/base.py` currently use a hardcoded `DATABASE_URL` for tests. This matches the plan. Later tasks will make the engine configuration environment-aware.
- The `Ingest` model includes a unique constraint on `(source, source_id)` for idempotent upserts.

## Global Constraints (verbatim)
- Python 3.12+
- No work data: all connectors must check a `personal_only=True` flag and refuse to initialize if false.
- Secrets in `.env` only: never commit keys; use `python-dotenv`.
- Every task ends with a passing test and a commit.
- Commit messages end with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- Local-first: all sensitive memory lives in local Postgres.
- Idempotent ingestion: every ingested item carries `source_id` and a content hash; re-syncs do not duplicate.
