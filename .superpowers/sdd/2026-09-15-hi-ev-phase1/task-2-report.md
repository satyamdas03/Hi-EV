# Task 2 Report: Database models and pgvector schema

## What was implemented

- `src/ev/db/__init__.py` — public exports for the database layer.
- `src/ev/db/base.py` — declarative `Base`, async `engine`, and `SessionLocal`.
  - Consumes `ev.config.get_settings().database_url` and converts `postgresql://` / `postgres://` URLs to `postgresql+asyncpg://` when needed.
  - Allows `EV_DATABASE_URL` to override the configured URL for tests/scripts.
- `src/ev/db/models.py` — ORM models:
  - `Ingest`: raw ingestion records with `source`, `source_id`, `content_hash`, and a unique constraint on `(source, source_id)` for idempotent re-syncs.
  - `Project`: structured project memory.
  - `Event`: episodic log entries with optional `project_id` FK.
  - All primary/foreign keys use SQLAlchemy 2's generic `Uuid` type so the same models work with Postgres (native UUID) and the test SQLite fallback.
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako` — async Alembic migration skeleton wired to `ev.config.get_settings().database_url`.
- `tests/test_db.py` — async test that creates a `Project`, commits, and reads it back.
- `tests/conftest.py` — forces tests to use an isolated async SQLite database so the suite runs without a local Postgres server.
- `pyproject.toml` — added `aiosqlite>=0.20.0` to the dev dependencies to support the async SQLite test fixture.
- `.gitignore` — added `*.db` to keep test SQLite artifacts out of the repo.

## TDD evidence

### RED (before implementation)

```text
$ cd C:/Users/point/projects/Hi-EV && python -m pytest tests/test_db.py::test_create_project -v
...
E   ModuleNotFoundError: No module named 'ev.db'
=========================== short test summary info ===========================
ERROR tests/test_db.py
============================== 1 error in 0.46s ===============================
```

### GREEN (after implementation)

```text
$ cd C:/Users/point/projects/Hi-EV && python -m pytest tests/test_db.py::test_create_project -v
...
tests/test_db.py::test_create_project PASSED                             [100%]
============================== 1 passed in 0.33s ==============================
```

### Full suite

```text
$ python -m pytest -v
...
tests/test_config.py::test_settings_loads_from_env PASSED                [ 50%]
tests/test_db.py::test_create_project PASSED                             [100%]
============================== 2 passed in 0.36s ==============================
```

## Files changed

- `src/ev/db/__init__.py` (new)
- `src/ev/db/base.py` (new)
- `src/ev/db/models.py` (new)
- `alembic.ini` (new)
- `alembic/env.py` (new)
- `alembic/script.py.mako` (new)
- `tests/test_db.py` (new)
- `tests/conftest.py` (new)
- `pyproject.toml` (added `aiosqlite` to dev deps)
- `.gitignore` (added `*.db`)

## Commits created

- `efaa942` — `feat: add async Postgres schema and pgvector models`
- `3453163` — `style: fix ruff lint issues in db and alembic files`

Both pushed to `origin/main`.

## Self-review findings

- All new Python files pass `ruff check`.
- The test fixture correctly creates and drops all tables per test.
- Models use generic `Uuid` and `DateTime(timezone=True)`, so they are dialect-agnostic enough for the SQLite fallback while still mapping to native Postgres types in production.
- Alembic env is async-ready and reads from `ev.config.get_settings().database_url`.

## Issues / concerns

- **No local Postgres server is running.** `psql` is not on `PATH`, no `postgresql` Windows service was found, and the project has no Docker-based Postgres running. Because of this, the test fixture uses an async SQLite database (`aiosqlite`) instead of the Postgres database the task brief nominally expects.
- **pgvector extension is not exercised yet.** The `pgvector` Python package is installed, but no `Vector` columns are modeled in this task; the plan only requires pgvector columns later. The current schema is pgvector-ready (Postgres target), but the SQLite fallback cannot test vector indexing.
- **Production readiness:** When a local Postgres + pgvector server is available, removing `EV_DATABASE_URL` from `tests/conftest.py` (or pointing it at `postgresql+asyncpg://localhost:5432/hiev_test`) will switch tests to the intended backend without any code changes.
