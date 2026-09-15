# Task 5 Report: GitHub personal repo ingestion

## What I implemented

Created `src/ev/ingestion/github.py` with the `GitHubIngestion` connector:

- Extends `ev.ingestion.base.IngestionSource`.
- Refuses to initialize unless `config.personal_only` is `True` via `ev.security.boundary.assert_personal_only`.
- Accepts one or more repos via `add_repo(owner, name)`.
- `add_repo` enforces the personal-only blocklist (`financialsimplicity` handle/domain), raising `PersonalOnlyError` for blocked owners or repos.
- `ingest()` is async, opens a single `httpx.AsyncClient`, and fetches:
  - `/repos/{owner}/{name}/commits`
  - `/repos/{owner}/{name}/issues?state=all`
  - `/repos/{owner}/{name}/pulls?state=all`
- Each record normalizes to:
  - `source`: `github_commits` | `github_issues` | `github_prs`
  - `source_id`: `{repo}:{id}`
  - `content_hash`: SHA-256 of the content
  - `content`: commit message, or issue/PR title + body
  - `project_tag`: repo name lowercased
  - `privacy_level`: `personal`
- Uses the GitHub token from `Settings.github_token` (SecretStr) as a Bearer header when present.
- Gracefully returns an empty list for non-2xx API responses.

Created `tests/test_ingestion_github.py` with four tests:

1. `test_github_ingestion_requires_personal_only` — verifies initialization fails when `personal_only=False`.
2. `test_github_ingestion_parses_commits` — mocks the three endpoints and confirms commit records are produced with the required provenance fields.
3. `test_github_ingestion_blocks_work_repos` — verifies the blocklist rejects a work owner.
4. `test_github_ingestion_parses_issues_and_prs` — verifies issues and PRs are normalized correctly.
5. `test_github_ingestion_handles_http_errors` — verifies 4xx responses yield no records instead of crashing.

## What I tested and test results

- Ran the new GitHub test module: `pytest tests/test_ingestion_github.py -v` — all 5 passed.
- Ran the full Hi-EV suite: `pytest -v` — **13 passed** (existing 8 + new 5).
- Ran `ruff check` on the new files — no issues.

## TDD Evidence

### RED

```bash
python -m pytest tests/test_ingestion_github.py -v
```

Output:

```
ERROR collecting tests/test_ingestion_github.py
ModuleNotFoundError: No module named 'ev.ingestion.github'
```

### GREEN

```bash
python -m pytest tests/test_ingestion_github.py -v
```

Output:

```
tests/test_ingestion_github.py::test_github_ingestion_requires_personal_only PASSED
tests/test_ingestion_github.py::test_github_ingestion_parses_commits PASSED
tests/test_ingestion_github.py::test_github_ingestion_blocks_work_repos PASSED
tests/test_ingestion_github.py::test_github_ingestion_parses_issues_and_prs PASSED
tests/test_ingestion_github.py::test_github_ingestion_handles_http_errors PASSED
```

## Files changed

- `src/ev/ingestion/github.py` (new)
- `tests/test_ingestion_github.py` (new)

## Self-review findings

- **Guard pattern:** The brief showed `personal_only_guard(config)` used as a plain call, but `personal_only_guard` is a `@contextmanager` and the Task 4 review parked switching to `assert_personal_only` directly. I used `assert_personal_only(config)`, which is consistent with the latest codebase direction and satisfies the test contract.
- **Test mocking refinement:** The brief’s single-mock-response test would crash when the same response was fed to the issues and pulls endpoints (commit JSON lacks a `number` key). I refined the test to return endpoint-appropriate responses via `side_effect` while preserving the brief’s assertions.
- **Base-class mismatch:** `IngestionSource.ingest()` is currently declared as a synchronous abstract method, but `GitHubIngestion.ingest()` is async. Python ABC only checks method existence at instantiation, so this does not fail now, but the base class should probably become async-aware (or split into sync/async sources) to keep the contract honest.
- **Workflow runs:** The task description mentions ingesting workflow runs, but the brief’s implementation and test do not include them. This is a scope gap to address in a later task or follow-up.
- **Pagination:** The connector caps each endpoint at `per_page=10` and does not follow `Link` headers. This matches the brief but will need pagination handling for real repos.
- **Blocklist precision:** The existing `Blocklist` uses substring matching. This is the established pattern in the repo, but it could produce false positives (e.g., a personal repo name containing a work handle substring).

## Issues or concerns

- The async `ingest()` override of a sync abstract method is a latent design inconsistency.
- Workflow-run ingestion is described in the task text but absent from the brief’s implementation and tests.
- No real GitHub API call has been exercised yet; the connector is validated only with mocks.

---

## Fix report: async ingestion interface

### Fix applied

Made `IngestionSource.ingest()` async so all ingestion sources share a uniform async interface.

- `src/ev/ingestion/base.py`:
  - Changed `def ingest(self)` to `async def ingest(self)`.
- `src/ev/ingestion/notes.py`:
  - Changed `NotesIngestion.ingest()` to `async def ingest(self)`; internal logic unchanged.
- `tests/test_ingestion_notes.py`:
  - Marked `test_notes_ingestion_finds_markdown` and `test_notes_ingestion_skips_blocklisted_files` as `async def` and added `await` to `ingester.ingest()` calls.

### Tests after fix

```bash
python -m pytest tests/test_ingestion_notes.py tests/test_ingestion_github.py -v
```

Output:

```
tests/test_ingestion_notes.py::test_notes_ingestion_finds_markdown PASSED
tests/test_ingestion_notes.py::test_notes_ingestion_refuses_non_personal_mode PASSED
tests/test_ingestion_notes.py::test_notes_ingestion_skips_blocklisted_files PASSED
tests/test_ingestion_github.py::test_github_ingestion_requires_personal_only PASSED
tests/test_ingestion_github.py::test_github_ingestion_parses_commits PASSED
tests/test_ingestion_github.py::test_github_ingestion_blocks_work_repos PASSED
tests/test_ingestion_github.py::test_github_ingestion_parses_issues_and_prs PASSED
tests/test_ingestion_github.py::test_github_ingestion_handles_http_errors PASSED
```

Full suite: `pytest -v` — **13 passed**.

### Additional files changed

- `src/ev/ingestion/base.py`
- `src/ev/ingestion/notes.py`
- `tests/test_ingestion_notes.py`

### Commit

- `fbf43e9` — fix(ingestion): make IngestionSource.ingest async and update NotesIngestion
