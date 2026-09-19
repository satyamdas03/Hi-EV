# Phase A Prep Sprint — Postgres + pgvector, Config Blocklist, Migration Discipline

> **Date:** 2026-09-17
> **Goal:** Clear the blockers so Phase A (Ambient Ingestion + Semantic Memory) can proceed without creating unrecoverable technical debt.

> **Update 2026-09-17:** Postgres 16 + pgvector was not installed in the environment and required user action, so the default local database was switched to **SQLite + sqlite-vec** instead. Postgres + pgvector remains an optional upgrade path via `EV_DATABASE_URL` and `scripts/setup_postgres.py`. All acceptance criteria below were met against the SQLite default.

> **Update 2026-09-17 (later):** Phase A proper is now complete and pushed to `origin/main`. See [`memory/hi-ev-phase-a-semantic-memory.md`](../../../memory/hi-ev-phase-a-semantic-memory.md) for the final shipped state.

---

## Why this prep sprint first

Phase A needs:
1. A database that supports vector search (pgvector).
2. A maintainable way to block work data, not hardcoded strings.
3. A migration workflow that does not edit old revisions once data exists.

Skipping these means building semantic memory on SQLite and then migrating later, or editing base migrations after production use. Both are expensive. This prep sprint is 1–2 days and prevents a much larger refactor later.

---

## Deliverables

### 1. Local Postgres + pgvector

**What:** Switch the local dev database from SQLite to Postgres 16 with the pgvector extension. Update `.env.example` and the actual `.env` file. Add a setup script for Windows/WSL.

**Rationale:** The README already targets Postgres + pgvector. SQLite was a test/dev convenience that will not support the semantic memory layer.

**Implementation:**
- Add `src/ev/db/pgvector_setup.py` or a SQL script that creates the `hiev` database and enables `pgvector` if run with sufficient privileges.
- Update `alembic.ini` to use `postgresql+asyncpg://localhost:5432/hiev` and ensure it matches `EV_DATABASE_URL`.
- Add `scripts/setup_postgres.py` that:
  - Connects to `postgres` or `template1` with a superuser.
  - Runs `CREATE DATABASE hiev;` and `CREATE EXTENSION IF NOT EXISTS vector;`.
  - Falls back to printing manual Windows/WSL instructions if Postgres is not installed.
- Add Windows setup instructions to the plan document and to `README.md`:
  - Option A: EDB Postgres installer from https://www.postgresql.org/download/windows/
  - Option B: `winget install PostgreSQL.PostgreSQL` if available.
  - Option C: WSL2 + `sudo apt install postgresql postgresql-contrib`.
  - For all options, enable pgvector: `CREATE EXTENSION vector;`.

**Acceptance criteria:**
- `python scripts/setup_postgres.py` reports the database exists and pgvector is enabled.
- `python -m alembic upgrade head` runs successfully against the local Postgres.
- `python -m pytest` still passes (tests will use SQLite; see Deliverable 2).

### 2. Test database isolation (keep tests on SQLite)

**What:** Ensure the test suite can run without a live Postgres server, using an isolated in-memory or file-based SQLite database, while the dev daemon uses Postgres.

**Rationale:** The README promises that tests fall back to SQLite. We need this to be true and clean so CI and local test runs do not depend on Postgres.

**Implementation:**
- Introduce a test-only engine/session factory or fixture override.
- Preferred approach: add `tests/conftest.py` fixtures that monkeypatch `EV_DATABASE_URL` to a test SQLite URL *before* `ev.db.base` is imported, or refactor `ev.db.base` so the engine is created lazily on first use and can be rebound.
- Simpler alternative: keep `ev.db.base` import-time engine, but add a `pytest_configure` hook that sets `EV_DATABASE_URL` to `sqlite+aiosqlite:///:memory:` (or a temp file) very early, then reloads `ev.db.base` or ensures it is imported after the env var is set.
- Add a `TEST_DATABASE_URL` default in `src/ev/config.py` only used when `PYTEST_CURRENT_TEST` is detected.
- Each test that needs tables uses `db_session` or `seeded_db` to create/drop.
- Update `README.md` setup section to clarify: tests use SQLite, dev uses Postgres.

**Acceptance criteria:**
- `python -m pytest` passes with no Postgres server running.
- `python -m evd` connects to Postgres when `EV_DATABASE_URL` is set to a Postgres URL.
- No test leaves tables or data in the dev Postgres database.

### 3. Config-driven work blocklist

**What:** Move the hardcoded `financialsimplicity` handles/domains out of `GitHubIngestion`, `GmailIngestion`, and `NotesIngestion` and into `Settings` + `.env`.

**Rationale:** The blocklist is a security control. Hardcoding it makes it easy to miss, impossible to update without a code change, and hard to audit.

**Implementation:**
- Add to `src/ev/config.py`:
  - `blocked_handles: list[str] = Field(default_factory=list)`
  - `blocked_domains: list[str] = Field(default_factory=list)`
  - Parse from comma-separated env vars `EV_BLOCKED_HANDLES` and `EV_BLOCKED_DOMAINS`.
- Update `src/ev/security/boundary.py`:
  - Add `from_settings(config: Settings) -> Blocklist` factory.
- Update ingestion sources to use `Blocklist.from_settings(config)` instead of inline lists.
- Update `.env.example` with example blocklist entries.
- Update existing tests in `tests/test_ingestion_github.py` and `tests/test_ingestion_notes.py` to pass a config with a test blocklist instead of relying on the default.

**Acceptance criteria:**
- No hardcoded `financialsimplicity` strings remain in `src/ev/ingestion/`.
- `EV_BLOCKED_HANDLES=foo,bar` in `.env` blocks those handles in all ingestion sources.
- Tests still verify blocklist behavior with a test-specific config.

### 4. Embedding model dependency

**What:** Add a local embedding model dependency and config so Phase A can compute document embeddings offline.

**Rationale:** Semantic memory needs embeddings. We want a small, fast model that runs on the RTX 5060 laptop with no cloud dependency.

**Implementation:**
- Add `sentence-transformers>=3.0.0` to `pyproject.toml` dependencies (or optional `local` extra).
- Add `EV_EMBEDDING_MODEL` setting defaulting to `all-MiniLM-L6-v2`.
- Create `src/ev/embeddings.py` with a thin `EmbeddingModel` wrapper:
  - `encode(texts: list[str]) -> list[list[float]]`
  - Lazy-loads the model on first call.
  - Handles batching and truncation.
- Add a smoke script `scripts/check_embeddings.py` that loads the model and encodes a few sentences to verify it works offline.

**Acceptance criteria:**
- `pip install -e ".[dev]"` installs `sentence-transformers`.
- `python scripts/check_embeddings.py` prints embedding dimensions without network calls.
- Model dimension is exposed as a constant (384 for all-MiniLM-L6-v2).

### 5. Migration discipline policy

**What:** Document and enforce the rule that Alembic base revisions are immutable once applied.

**Rationale:** We already edited the base migration to fix missing columns. That is acceptable once, but doing it again after real data exists is dangerous.

**Implementation:**
- Add a section to `docs/superpowers/assessments/2026-09-17-hi-ev-honest-state-and-roadmap.md` or a new `docs/development/migrations.md` file:
  - Base revision `aacdc9089a90` is now frozen.
  - All future schema changes must be generated via `alembic revision --autogenerate -m "..."`.
  - Never edit an already-applied migration.
  - For local dev resets, use `alembic downgrade base` or recreate the database.
- Add a CI check (if/when CI exists) that fails if an applied migration file is modified.

**Acceptance criteria:**
- Migration policy document exists and is linked from `README.md`.
- Team understands that any schema change needs a new migration.

### 6. Update README setup instructions

**What:** Refresh `README.md` setup so a new user can install Postgres + pgvector, configure `.env`, run migrations, and start the daemon.

**Implementation:**
- Replace the SQLite fallback note with explicit Postgres-first setup.
- Keep the note that tests use SQLite automatically.
- Add the blocklist env vars.
- Add the embedding model env var.

**Acceptance criteria:**
- A new user can follow `README.md` from a fresh clone to a running daemon.

---

## Order of work

1. **Test DB isolation** — do this first so subsequent changes can be tested safely.
2. **Config-driven blocklist** — small, safe, removes hardcoded security data.
3. **Embedding dependency + smoke script** — adds the model, verifies offline loading.
4. **Postgres + pgvector setup** — requires user to install Postgres; may take the longest due to environment setup.
5. **Migration discipline document + README updates** — do last so it reflects the final state.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Postgres not installed in current environment | Provide clear Windows/WSL/Linux install steps; the actual install is user action. |
| Tests accidentally touch dev Postgres | Fix test DB isolation first; add a fixture that asserts `aiosqlite` is used in tests. |
| sentence-transformers too large for the repo/CI | It is downloaded on first use, not committed. Pin model name, cache in `~/.cache`. |
| Blocklist tests break when default changes | Update tests to inject a test config with explicit blocklist. |
| pgvector extension not available after Postgres install | Document `CREATE EXTENSION vector;` and provide `setup_postgres.py` to run it. |

---

## Acceptance criteria for the prep sprint

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `python -m pytest` passes with no Postgres running. | ✅ 89 passed, 1 skipped |
| 2 | `python -m alembic upgrade head` succeeds against the local database. | ✅ Verified against SQLite + sqlite-vec; Postgres + pgvector path documented |
| 3 | `python scripts/check_embeddings.py` prints embedding dimensions. | ✅ 384-dim vectors from `all-MiniLM-L6-v2` |
| 4 | `ruff check src tests scripts` is clean. | ✅ |
| 5 | No hardcoded work blocklist strings in `src/ev/ingestion/`. | ✅ |
| 6 | `README.md` and migration policy documents are updated. | ✅ |
| 7 | `python scripts/setup_sqlite_vec.py` creates DB and vector table. | ✅ |
| 8 | `python scripts/smoke_vector_search.py` returns top-K results. | ✅ |

---

## What unlocks after this sprint

Phase A proper is now unblocked:
- Document chunking pipeline.
- Populate `DocumentChunk` rows and index embeddings in sqlite-vec.
- Hybrid search (BM25 + vector + rerank).
- Continuous ingestion scheduler.
- `ev remember` command.

When Postgres is installed later, a single Alembic revision can migrate the sqlite-vec virtual table to a pgvector `vector(384)` column. The embedding model, dimensions, and `DocumentChunk` schema stay the same.
