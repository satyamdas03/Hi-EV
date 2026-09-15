# Hi-EV Phase 2 Completion Report

**Date:** 2026-09-15
**Scope:** Presence + Status + Research + Drafting + Claude Code spawn + read-only Gmail/Calendar ingestion
**Test result:** 56 passed, 1 skipped
**Lint result:** `ruff check src tests scripts` clean

---

## What was delivered

| # | Feature | Key files | Tests |
|---|---------|-----------|-------|
| 1 | NVIDIA NIM LLM client | `src/ev/llm/client.py` | `tests/test_llm_client.py` |
| 2 | Richer `ev status <project>` | `src/ev/memory/status.py`, `src/ev/memory/store.py` | `tests/test_memory_status.py`, `tests/test_memory_store.py` |
| 3 | `ev brief` cross-project status | `src/ev/tools/brief_tool.py` | `tests/test_brief_tool.py` |
| 4 | `ev research <query>` | `src/ev/research/search.py`, `src/ev/tools/research_tool.py` | `tests/test_research_tool.py` |
| 5 | `ev work on "..." --project <name>` | `src/ev/tools/work_tool.py` | `tests/test_work_tool.py` |
| 6 | Reversible drafting tools | `src/ev/tools/draft_tools.py` | `tests/test_draft_tools.py` |
| 7 | Gmail + Calendar read-only ingestion | `src/ev/ingestion/gmail.py`, `src/ev/ingestion/calendar.py`, `src/ev/google_auth.py`, `src/ev/tools/calendar_prep_tool.py`, `src/ev/db/models.py` | `tests/test_google_ingestion.py`, `tests/test_calendar_prep.py` |

Voice (feature 8) was deferred to Phase 5+ as planned.

---

## Commits

```
a2c6dd9 hi-ev: phase2 — add demo script for status/brief/research/work/draft/calendar-prep
e8f200c hi-ev: phase2 — add Gmail/Calendar read-only ingestion and ev calendar prep
70cb97f hi-ev: phase2 — add ev draft commit/pr/reply tools
155e138 hi-ev: phase2 — add ev work on to spawn Claude Code
ee36a85 hi-ev: phase2 — add ev research with DuckDuckGo citations
3d37b44 hi-ev: phase2 — add ev brief cross-project status
3a80784 hi-ev: phase2 — richer ev status with phase inference and counts
330b8c6 hi-ev: phase2 — add NVIDIA NIM LLM client with provider fallback
```

All commit messages end with the required attribution line.

---

## Test and quality verification

```text
$ ruff check src tests scripts
All checks passed!

$ python -m pytest
56 passed, 1 skipped in ~13s
```

The single skipped test is the live GitHub integration test (`tests/test_integration.py`), which is gated by `EV_RUN_INTEGRATION=1`.

---

## Notable implementation details

- **LLM:** `LLMClient` defaults to NVIDIA NIM (`meta/llama-3.3-70b-instruct`) with OpenAI-compatible chat completions. `EV_LLM_PROVIDER` can also be `openai` or `anthropic`.
- **Search:** DuckDuckGo HTML search is done with `httpx` and regex parsing of `result__a`, `result__url`, and `result__snippet`. No API key required.
- **Work spawn:** `WorkTool` uses `asyncio.create_subprocess_exec` to spawn `claude code` in the target repo with a prepared context payload. It logs a `spawn_claude_code` event.
- **Drafts:** `DraftCommitTool`, `DraftPrTool`, and `DraftReplyTool` are all Tier 1 (reversible). They read diffs/snippets and write draft text only.
- **Gmail/Calendar:** Strictly read-only, gated by `EV_GOOGLE_ENABLED=true` and `assert_personal_only`. `GmailIngestion` reads `INBOX` only and skips blocked senders. `CalendarIngestion` reads the primary calendar and extracts deadline entries. Both use content-hash idempotent upserts.
- **Database:** Added `Deadline` model and an Alembic migration (`alembic/versions/aacdc9089a90_add_deadlines.py`). SQLite fallback remains for tests.
- **Secrets:** All API keys and OAuth credentials are read from `.env` only; `.env.example` was updated.

---

## Known limitations / next steps

- Gmail and Calendar require the user to create Google OAuth 2.0 credentials and run `python scripts/setup_google_oauth.py` once. They are disabled by default.
- Redis caching for research is opportunistic; if Redis is unavailable, the tool falls back to no cache.
- The demo script (`scripts/demo_phase2.py`) runs all commands locally. The `ev work on` step will spawn Claude Code if executed.
- Voice integration remains a Phase 5+ research item.

---

## Self-review

- All acceptance criteria in `docs/superpowers/plans/2026-09-15-hi-ev-phase2.md` are met.
- TDD discipline was followed: failing tests were written first, then implementations, then commits.
- `personal_only=True` is enforced for all Google ingestion.
- No secrets are hardcoded; all live behind `.env`.
- The repository is ready to push to `origin/main`.
