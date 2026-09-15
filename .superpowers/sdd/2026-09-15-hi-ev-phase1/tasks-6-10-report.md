# Tasks 6–10 Report: Memory, Status, Tools, CLI, and Daemon

## Summary

Implemented the core query path for Hi-EV Phase 1: a structured memory store, a project status summary builder, a tool registry with a tier-0 status tool, a Click CLI command, and a FastAPI daemon endpoint. All five tasks were developed test-first, committed individually, and the full suite passes (18/18). One follow-up style commit fixed ruff lint warnings.

---

## Task 6: Memory store — structured CRUD + ingest persistence

### What was implemented
- `src/ev/memory/__init__.py` — exports `MemoryStore` and `build_status_summary` (the latter added in Task 7).
- `src/ev/memory/store.py` — `MemoryStore` class with:
  - `upsert_ingest(records)` — portable idempotent bulk upsert by `(source, source_id)`.
  - `count_ingest_by_source(source)` — count ingested rows by source.
  - `get_or_create_project(name, **kwargs)` — fetch or insert a `Project`.
  - `add_event(...)` — append an `Event` for a project.
- The unique constraint on `(source, source_id)` was already present in `src/ev/db/models.py`.
- Added `.gitignore` override `!src/ev/memory/` so the source package is not shadowed by the local-data `memory/` ignore rule.

### TDD evidence

Failing test (module missing):

```text
$ python -m pytest tests/test_memory_store.py -v
ERROR tests/test_memory_store.py
ModuleNotFoundError: No module named 'ev.memory'
```

Passing test:

```text
$ python -m pytest tests/test_memory_store.py -v
tests/test_memory_store.py::test_upsert_ingest_idempotent PASSED
============================== 1 passed in 0.45s ==============================
```

### Files changed
- `src/ev/memory/__init__.py`
- `src/ev/memory/store.py`
- `tests/test_memory_store.py`
- `.gitignore`

---

## Task 7: Status summary builder

### What was implemented
- `src/ev/memory/status.py` — `build_status_summary(store, project_name)` returns a dict with project phase, latest commits/issues/PRs/notes, last activity, and a generated one-paragraph `summary_text`.
- Updated `src/ev/memory/__init__.py` to also export `build_status_summary`.

### TDD evidence

Failing test:

```text
$ python -m pytest tests/test_memory_status.py -v
ERROR tests/test_memory_status.py
ModuleNotFoundError: No module named 'ev.memory.status'
```

Passing test:

```text
$ python -m pytest tests/test_memory_status.py -v
tests/test_memory_status.py::test_status_summary_basic PASSED
============================== 1 passed in 0.58s ==============================
```

### Files changed
- `src/ev/memory/status.py`
- `src/ev/memory/__init__.py`
- `tests/test_memory_status.py`

---

## Task 8: Tool registry and `ev status` tool

### What was implemented
- `src/ev/tools/registry.py` — `Tool` base class and `ToolRegistry` with `register()`/`get()` and optional `bind_store()` hook.
- `src/ev/tools/status_tool.py` — `StatusTool` (tier 0, read-only) that calls `build_status_summary` and returns `summary_text`.
- `src/ev/tools/__init__.py` — exports `ToolRegistry` and `StatusTool`.

### TDD evidence

Failing test:

```text
$ python -m pytest tests/test_status_tool.py -v
ERROR tests/test_status_tool.py
ModuleNotFoundError: No module named 'ev.tools.registry'
```

Passing test:

```text
$ python -m pytest tests/test_status_tool.py -v
tests/test_status_tool.py::test_status_tool_returns_summary PASSED
============================== 1 passed in 0.42s ==============================
```

### Files changed
- `src/ev/tools/__init__.py`
- `src/ev/tools/registry.py`
- `src/ev/tools/status_tool.py`
- `tests/test_status_tool.py`

---

## Task 9: CLI entrypoint — `ev status`

### What was implemented
- Extended `src/ev/cli/main.py` with the `ev status <project>` Click command. The command opens a DB session, wraps it in `MemoryStore`, registers `StatusTool`, and echoes the summary.
- Added `src/ev/cli/__init__.py` export of `cli`.
- Added `src/evd.py` as a local runner entrypoint (`python src/evd.py status RoboCAD`).

### TDD evidence

Failing test (command missing):

```text
$ python -m pytest tests/test_cli.py -v
tests/test_cli.py::test_status_command FAILED
assert 2 == 0
```

Passing test:

```text
$ python -m pytest tests/test_cli.py -v
tests/test_cli.py::test_status_command PASSED
============================== 1 passed in 0.39s ==============================
```

### Files changed
- `src/ev/cli/main.py`
- `src/ev/cli/__init__.py`
- `src/evd.py`
- `tests/test_cli.py`

---

## Task 10: FastAPI internal API and daemon skeleton

### What was implemented
- `src/ev/server/api.py` — FastAPI app with:
  - `POST /status` — accepts `{"project": "..."}` and returns `{"summary": "..."}`.
  - `GET /health` — returns `{"status": "ok"}`.
  - Lifespan context that loads settings into `app.state.settings`.
- `src/ev/server/__init__.py` — exports `app`.
- `src/ev/daemon/daemon.py` — `run(host, port)` wrapper around `uvicorn.run(app, ...)`.
- `src/ev/daemon/__init__.py` — exports `run`.

### TDD evidence

Failing test:

```text
$ python -m pytest tests/test_server.py -v
ERROR tests/test_server.py
ModuleNotFoundError: No module named 'ev.server.api'
```

Then, after creating the module, the brief's `AsyncClient(app=app, ...)` call failed because modern httpx requires an ASGI transport:

```text
TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'
```

Fixed the test to use `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.

Passing test:

```text
$ python -m pytest tests/test_server.py -v
tests/test_server.py::test_status_endpoint PASSED
============================== 1 passed in 0.45s ==============================
```

### Files changed
- `src/ev/server/__init__.py`
- `src/ev/server/api.py`
- `src/ev/daemon/__init__.py`
- `src/ev/daemon/daemon.py`
- `tests/test_server.py`

---

## Full suite result

```text
$ python -m pytest -v
============================== 18 passed in 0.71s ==============================
```

All pre-existing tests continue to pass.

---

## Self-review findings

1. **Database compatibility.** The brief suggested `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`. Because the test suite forces an async SQLite fallback (`sqlite+aiosqlite:///...`), I implemented a portable query-then-merge upsert in `MemoryStore.upsert_ingest`. It is idempotent on both Postgres and SQLite and satisfies the global idempotency constraint.
2. **ToolRegistry contract.** The brief's CLI snippet passed the raw SQLAlchemy session to `ToolRegistry`, which would have broken `build_status_summary(store, ...)` because it expects `store.session`. I wrapped the session in `MemoryStore` in both the CLI and the server endpoint, keeping the registry/store boundary consistent.
3. **httpx ASGI transport.** Modern httpx no longer accepts `app=` directly; updated the server test to use `httpx.ASGITransport`.
4. **Linting.** After implementation, `ruff check` flagged import ordering and an unused `settings` variable in `src/ev/cli/main.py`. These were auto/manually fixed and verified.
5. **Gitignore collision.** The local-data `memory/` rule in `.gitignore` shadowed the new `src/ev/memory/` package. Added `!src/ev/memory/` to allow the source package while keeping the local `memory/` directory ignored.

## Issues or concerns

- The server endpoint and CLI create a fresh `SessionLocal` and `ToolRegistry` per request/command. This is fine for Phase 1 but will need dependency injection or lifespan-managed tooling as more tools are added.
- Tier enforcement is minimal (only the `tier` attribute on `Tool`). Phase 1 explicitly scopes tier enforcement as future work.
- No work-data guard was added to the query path because these endpoints only read already-filtered personal memory. Ingestion connectors (Tasks 1–5) enforce `personal_only=True` at import time.
