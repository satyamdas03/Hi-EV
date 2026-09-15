# Tasks 6–10: Memory, Status, Tools, CLI, and Daemon

This is a batched implementation brief for five tightly-coupled tasks. Implement them in order, commit after each task, and run the focused tests for each task before moving on.

## Task 6: Memory store — structured CRUD + ingest persistence

**Files:**
- Create: `src/ev/memory/store.py`
- Modify: `src/ev/db/models.py` — ensure unique constraint on `(source, source_id)` exists.
- Test: `tests/test_memory_store.py`

**Interfaces:**
- Consumes: `ev.db.SessionLocal`, `ev.db.models.Ingest`, `ev.db.models.Project`.
- Produces:
  - `ev.memory.store.MemoryStore` class.
  - `MemoryStore.upsert_ingest(records)` — bulk upsert by `(source, source_id)`.
  - `MemoryStore.get_or_create_project(name, **kwargs)` → `Project`.
  - `MemoryStore.add_event(project_name, event_type, description, source_url)` → `Event`.
  - `MemoryStore.count_ingest_by_source(source)` → `int`.

**Test:**

```python
# tests/test_memory_store.py
import pytest
from ev.config import Settings
from ev.db.base import Base, engine, SessionLocal
from ev.memory.store import MemoryStore

@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def test_upsert_ingest_idempotent(store):
    records = [
        {"source": "github_commits", "source_id": "RoboCAD:abc", "content_hash": "h1", "content": "feat: x", "project_tag": "robocad", "privacy_level": "personal"}
    ]
    await store.upsert_ingest(records)
    await store.upsert_ingest(records)
    count = await store.count_ingest_by_source("github_commits")
    assert count == 1
```

**Implementation:**

```python
# src/ev/memory/__init__.py
from .store import MemoryStore
from .status import build_status_summary

__all__ = ["MemoryStore", "build_status_summary"]

# src/ev/memory/store.py
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from ev.db.models import Event, Ingest, Project

class MemoryStore:
    def __init__(self, session):
        self.session = session

    async def upsert_ingest(self, records: list[dict]) -> int:
        if not records:
            return 0
        stmt = insert(Ingest).values(records)
        upsert = stmt.on_conflict_do_update(
            index_elements=["source", "source_id"],
            set_={"content_hash": stmt.excluded.content_hash, "content": stmt.excluded.content, "updated_at": Ingest.updated_at},
        )
        await self.session.execute(upsert)
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
```

**Commit:**
```bash
git add src/ev/memory/store.py tests/test_memory_store.py src/ev/db/models.py
git commit -m "feat: add memory store with idempotent ingest upsert" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 7: Status summary builder

**Files:**
- Create: `src/ev/memory/status.py`
- Test: `tests/test_memory_status.py`

**Interfaces:**
- Consumes: `ev.memory.store.MemoryStore`.
- Produces: `ev.memory.status.build_status_summary(store, project_name)` → `dict`.

**Test:**

```python
# tests/test_memory_status.py
import pytest
from ev.db.base import Base, engine, SessionLocal
from ev.memory.store import MemoryStore
from ev.memory.status import build_status_summary

@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def test_status_summary_basic(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_url="https://github.com/satyamdas03/RoboCAD")
    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1", "content": "feat: Phase 29 delivered", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_issues", "source_id": "RoboCAD:42", "content_hash": "h2", "content": "bug: mesh fails", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    summary = await build_status_summary(store, "RoboCAD")
    assert summary["name"] == "RoboCAD"
    assert summary["phase"] == "Phase 29"
    assert any("Phase 29 delivered" in c["content"] for c in summary["latest_commits"])
    assert len(summary["open_issues"]) == 1
```

**Implementation:**

```python
# src/ev/memory/status.py
from sqlalchemy import desc, select
from ev.db.models import Ingest, Project

async def build_status_summary(store, project_name: str) -> dict:
    result = await store.session.execute(select(Project).where(Project.name == project_name))
    project = result.scalar_one_or_none()
    if project is None:
        return {"name": project_name, "phase": None, "error": "Project not found in memory"}

    tag = project_name.lower()
    stmt = select(Ingest).where(Ingest.project_tag == tag).order_by(desc(Ingest.updated_at))
    result = await store.session.execute(stmt)
    rows = result.scalars().all()

    commits = [r for r in rows if r.source == "github_commits"][:5]
    issues = [r for r in rows if r.source == "github_issues"][:5]
    prs = [r for r in rows if r.source == "github_prs"][:5]
    notes = [r for r in rows if r.source == "notes"][:3]

    def to_dict(r):
        return {"source": r.source, "source_id": r.source_id, "content": r.content, "updated_at": r.updated_at.isoformat()}

    latest = rows[0].updated_at if rows else None
    summary_text = _make_summary_text(project, commits, issues, prs, notes)

    return {
        "name": project.name,
        "phase": project.current_phase,
        "latest_commits": [to_dict(c) for c in commits],
        "open_issues": [to_dict(i) for i in issues],
        "open_prs": [to_dict(p) for p in prs],
        "recent_notes": [to_dict(n) for n in notes],
        "last_activity": latest.isoformat() if latest else None,
        "summary_text": summary_text,
    }

def _make_summary_text(project, commits, issues, prs, notes):
    parts = [f"{project.name} is at {project.current_phase or 'unknown phase'}."]
    if commits:
        parts.append(f"Latest commit: {commits[0].content.splitlines()[0][:80]}.")
    if issues:
        parts.append(f"{len(issues)} recent issue(s).")
    if prs:
        parts.append(f"{len(prs)} recent PR(s).")
    if notes:
        parts.append(f"{len(notes)} recent note(s).")
    return " ".join(parts)
```

**Commit:**
```bash
git add src/ev/memory/status.py tests/test_memory_status.py
git commit -m "feat: add project status summary builder" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 8: Tool registry and `ev status` tool

**Files:**
- Create: `src/ev/tools/registry.py`
- Create: `src/ev/tools/status_tool.py`
- Test: `tests/test_status_tool.py`

**Interfaces:**
- Consumes: `ev.memory.store.MemoryStore`, `ev.memory.status.build_status_summary`.
- Produces:
  - `ev.tools.registry.ToolRegistry` class.
  - `ev.tools.registry.Tool` base class with `name`, `tier`, `description`.
  - `ev.tools.status_tool.StatusTool` class.
  - `StatusTool.run(project)` → summary text.

**Test:**

```python
# tests/test_status_tool.py
import pytest
from ev.db.base import Base, engine, SessionLocal
from ev.memory.store import MemoryStore
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool

@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def test_status_tool_returns_summary(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
    await store.upsert_ingest([{
        "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
        "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
    }])
    registry = ToolRegistry(store)
    registry.register(StatusTool())
    result = await registry.get("status").run(project="RoboCAD")
    assert "Phase 29" in result
    assert "deliver Phase 29" in result
```

**Implementation:**

```python
# src/ev/tools/__init__.py
from .registry import ToolRegistry
from .status_tool import StatusTool

__all__ = ["ToolRegistry", "StatusTool"]

# src/ev/tools/registry.py
from typing import Any

class Tool:
    def __init__(self, name: str, tier: int, description: str):
        self.name = name
        self.tier = tier
        self.description = description

    async def run(self, **kwargs) -> Any:
        raise NotImplementedError

class ToolRegistry:
    def __init__(self, store):
        self.store = store
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        if hasattr(tool, "bind_store"):
            tool.bind_store(self.store)

    def get(self, name: str) -> Tool:
        return self._tools[name]

# src/ev/tools/status_tool.py
from ev.memory.status import build_status_summary
from .registry import Tool

class StatusTool(Tool):
    def __init__(self):
        super().__init__(name="status", tier=0, description="Get a one-paragraph status update for a project")

    def bind_store(self, store):
        self.store = store

    async def run(self, project: str) -> str:
        summary = await build_status_summary(self.store, project)
        return summary["summary_text"]
```

**Commit:**
```bash
git add src/ev/tools/ tests/test_status_tool.py
git commit -m "feat: add tool registry and ev status tool" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 9: CLI entrypoint — `ev status`

**Files:**
- Create: `src/ev/cli/main.py`
- Create: `src/evd.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ev.config.get_settings()`, `ev.db.SessionLocal`, `ev.tools.registry.ToolRegistry`, `ev.tools.status_tool.StatusTool`.
- Produces: `ev status <project>` command via Click.

**Test:**

```python
# tests/test_cli.py
import pytest
from click.testing import CliRunner
from ev.cli.main import cli
from ev.db.base import Base, engine, SessionLocal
from ev.memory.store import MemoryStore

@pytest.fixture
async def seeded_store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
        await store.upsert_ingest([{
            "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
            "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
        }])
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

def test_status_command(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "RoboCAD"])
    assert result.exit_code == 0
    assert "RoboCAD" in result.output
    assert "Phase 29" in result.output
```

**Implementation:**

```python
# src/ev/cli/__init__.py
from .main import cli

__all__ = ["cli"]

# src/ev/cli/main.py
import asyncio
import click
from ev.config import get_settings
from ev.db.base import SessionLocal
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool

@click.group()
def cli():
    pass

@cli.command()
@click.argument("project")
def status(project: str):
    async def _run():
        settings = get_settings()
        async with SessionLocal() as session:
            registry = ToolRegistry(session)
            registry.register(StatusTool())
            result = await registry.get("status").run(project=project)
            click.echo(result)
    asyncio.run(_run())

# src/evd.py
from ev.cli.main import cli

if __name__ == "__main__":
    cli()
```

**Commit:**
```bash
git add src/ev/cli/ src/evd.py tests/test_cli.py
git commit -m "feat: add ev status CLI command" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 10: FastAPI internal API and daemon skeleton

**Files:**
- Create: `src/ev/server/api.py`
- Create: `src/ev/daemon/daemon.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `ev.tools.registry.ToolRegistry`, `ev.tools.status_tool.StatusTool`, `ev.config.get_settings`.
- Produces:
  - `POST /status` with JSON body `{"project": "RoboCAD"}` → `{"summary": "..."}`.
  - `GET /health` health check.
  - `evd` daemon entrypoint.

**Test:**

```python
# tests/test_server.py
import pytest
from httpx import AsyncClient
from ev.server.api import app

@pytest.fixture
async def seeded_db():
    from ev.db.base import Base, engine, SessionLocal
    from ev.memory.store import MemoryStore
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
        await store.upsert_ingest([{
            "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
            "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
        }])
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def test_status_endpoint(seeded_db):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/status", json={"project": "RoboCAD"})
        assert response.status_code == 200
        assert "RoboCAD" in response.json()["summary"]
```

**Implementation:**

```python
# src/ev/server/__init__.py
from .api import app

__all__ = ["app"]

# src/ev/server/api.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from ev.config import get_settings
from ev.db.base import SessionLocal
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    yield {}

app = FastAPI(title="EV Daemon API", lifespan=lifespan)

class StatusRequest(BaseModel):
    project: str

@app.post("/status")
async def status_endpoint(req: StatusRequest):
    async with SessionLocal() as session:
        registry = ToolRegistry(session)
        registry.register(StatusTool())
        summary = await registry.get("status").run(project=req.project)
        return {"summary": summary}

@app.get("/health")
async def health():
    return {"status": "ok"}

# src/ev/daemon/__init__.py
from .daemon import run

__all__ = ["run"]

# src/ev/daemon/daemon.py
import uvicorn
from ev.server.api import app

def run(host: str = "127.0.0.1", port: int = 7345):
    uvicorn.run(app, host=host, port=port)
```

**Commit:**
```bash
git add src/ev/server/ src/ev/daemon/ tests/test_server.py
git commit -m "feat: add FastAPI daemon API and evd entrypoint" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

## Important Notes for the Batch

- Use SQLite async fallback for tests if local Postgres is not available, as was accepted in Task 2.
- Ensure the DB fixture creates/drops tables per test to avoid state leakage.
- The `StatusTool` is Tier 0 (read-only). Tier enforcement is minimal in Phase 1.

## Global Constraints (verbatim)
- Python 3.12+
- No work data: all connectors must check a `personal_only=True` flag and refuse to initialize if false.
- Secrets in `.env` only: never commit keys; use `python-dotenv`.
- Every task ends with a passing test and a commit.
- Commit messages end with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- Local-first: all sensitive memory lives in local Postgres.
- Idempotent ingestion: every ingested item carries `source_id` and a content hash; re-syncs do not duplicate.
