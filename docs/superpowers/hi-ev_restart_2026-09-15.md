---
name: hi-ev_restart_2026-09-15
description: "EV / Hi-EV full session recovery dossier — read this first when restarting a fresh session."
metadata:
  node_type: memory
  type: reference
  originSessionId: c391edcd-a13c-4b1e-a13a-14088c80d1a3
  created: 2026-09-15
  modified: 2026-09-16T00:00:00+10:00
---

# EV / Hi-EV — Full Session Recovery Dossier

**Read this first** when a new Claude session starts with no context of this project.

> **Mirror location:** this file is kept in sync with `C:/Users/point/.claude/projects/C--Users-point/memory/hi-ev_restart_2026-09-15.md`. Update both copies when editing.

---

## 1. What EV is

**EV** is a personal, local-first AI operating system that runs on Satyam's RTX 5060 laptop. It is not a chatbot. It is meant to be a persistent cognitive layer above all personal projects.

When the laptop opens, EV is supposed to:
- Have already read overnight changes in personal repos.
- Know deadlines and upcoming meetings.
- Speak first (eventually via voice).
- Execute reversible work automatically (draft PRs, run tests, summarize emails, schedule focus time).
- Keep consequential actions behind explicit confirmation.

EV operates under a **strict personal-only boundary** — no work email, work Slack, work repos, or employer IP/patent data. This is enforced in code via `assert_personal_only()` and a `Blocklist`.

---

## 2. Repository location and key files

**Repo path:** `C:/Users/point/projects/Hi-EV`
**Remote:** `https://github.com/satyamdas03/Hi-EV`
**Branch:** `main`

Key directories and files:
- `src/ev/` — all source code.
- `src/ev/cli/main.py` — CLI entry point (`ev` commands).
- `src/ev/daemon/daemon.py` — FastAPI daemon runner.
- `src/ev/server/api.py` — FastAPI routes.
- `src/ev/config.py` — Pydantic settings; includes Google OAuth + alert-loop flags.
- `src/ev/db/models.py` — SQLAlchemy models (`Ingest`, `Project`, `Event`, `Deadline`, `Person`, `Obligation`, `Decision`).
- `src/ev/db/base.py` — `Base`, `SessionLocal`, `engine`.
- `src/ev/memory/store.py` — `MemoryStore` with idempotent upsert for all structured tables.
- `src/ev/memory/status.py` — `build_status_summary()` for status/brief; includes upcoming deadline counts.
- `src/ev/llm/client.py` — async OpenAI-compatible LLM client (NVIDIA NIM default).
- `src/ev/ingestion/github.py`, `notes.py`, `gmail.py`, `calendar.py`, `google_auth.py` — ingestion connectors.
- `src/ev/tools/` — tools: `status_tool.py`, `brief_tool.py`, `research_tool.py`, `work_tool.py`, `draft_tools.py`, `calendar_prep_tool.py`, `deadline_watcher.py`, `alerts_tool.py`, `people_tool.py`, `obligations_tool.py`, `prep_tool.py`.
- `tests/` — pytest suite.
- `scripts/`:
  - `seed_demo.py` — seeds GitHub + notes data; updates `Project.repo_path` from env vars.
  - `test_nvidia_models.py` — probes which NVIDIA NIM models work with the provided key.
  - `google_auth.py` — standalone browser OAuth flow; saves `secrets/token.json`.
  - `sync_google.py` — ingests live Gmail + Calendar into EV memory.
- `docs/superpowers/plans/2026-09-15-hi-ev-phase2.md` — completed Phase 2 plan.
- `docs/superpowers/plans/2026-09-15-hi-ev-phase3.md` — completed Phase 3 plan.
- `docs/superpowers/research/2026-09-15-nvidia-api-livekit-voice.md` — research on NVIDIA models + voice options.
- `docs/superpowers/hi-ev_restart_2026-09-15.md` — mirror of this dossier.
- `.superpowers/sdd/2026-09-15-hi-ev-phase2/report.md` — Phase 2 completion report.
- `pyproject.toml` — hatchling packaging, pytest config.

---

## 3. Secrets and environment

All secrets live in `C:/Users/point/projects/Hi-EV/.env` (gitignored). Do not hardcode secrets in source files.

Known values in `.env` as of this session (see the actual `.env` file; never commit real tokens):
- `EV_GITHUB_TOKEN=[REDACTED — see .env; rotate after this session]` — classic personal token.
- `EV_NVIDIA_API_KEY=[REDACTED — see .env]`
- `EV_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
- `EV_DATABASE_URL=sqlite+aiosqlite:///C:/Users/point/projects/Hi-EV/hiev.db`
- `EV_NOTES_PATH=C:/Users/point/notes`
- `EV_GOOGLE_ENABLED=true`
- `EV_GOOGLE_CREDENTIALS_PATH=C:/Users/point/projects/Hi-EV/secrets/credentials.json`
- Alert-loop settings:
  - `EV_ALERT_INTERVAL_SEC=900`
  - `EV_ALERT_WINDOW_HOURS=72`
  - `EV_QUIET_START=22:00`
  - `EV_QUIET_END=08:00`
  - `EV_KILL_SWITCH=false`
- Repo paths:
  - `EV_ROBOCAD_PATH=C:/Users/point/projects/RoboCAD`
  - `EV_LEARNINGROBOTICS_PATH=C:/Users/point/projects/LearningRobotics`
  - `EV_HIEV_PATH=C:/Users/point/projects/Hi-EV`

OAuth files (also gitignored):
- `C:/Users/point/projects/Hi-EV/secrets/credentials.json` — Google Desktop app client secret.
- `C:/Users/point/projects/Hi-EV/secrets/token.json` — user access token from completed OAuth flow.

Add `.env` values and OAuth files only; never paste them into code or memory files.

---

## 4. Current phase and status

**Phase 3 is complete and pushed.** Real-time Google sync is live and Phase 3 structured-memory features are implemented.

Latest commit: `cf3f158`.
Key prior commits:
- `0ce429f` — Phase 3 plan.
- `6b1e0c4` — session recovery dossier mirror.
- `da02b46` — NVIDIA model + repo path fixes.
- Phase 3 commit (pending) — `Person`, `Obligation`, `Decision`, deadline watcher, alerts, prep tools.

Test result:
- `python -m pytest` → **82 passed, 1 skipped**.
- `ruff check src tests scripts` → clean.

Live data in EV memory:
- 30 GitHub records (RoboCAD, LearningRobotics, Hi-EV) from `seed_demo.py`.
- 20 Gmail messages from personal inbox via `scripts/sync_google.py` → 16 `Person` rows.
- 30 Google Calendar events → 30 extracted `Deadline` rows.

Daemon state:
- EV daemon should be running on `http://127.0.0.1:7345`.
- Health endpoint: `GET /health` returns `{"status":"ok"}`.
- Routes available: `/status`, `/brief`, `/research`, `/work`, `/draft`, `/calendar-prep`, `/deadlines`, `/people`, `/obligations`, `/alerts`, `/prep`, `/health`.

---

## 5. What was delivered today

### Phase 2 features (all complete)

1. **NVIDIA NIM LLM client** (`src/ev/llm/client.py`, `tests/test_llm_client.py`).
   - Thin async OpenAI-compatible wrapper.
   - Default provider: `nvidia` using `https://integrate.api.nvidia.com/v1`.
   - Default model: `meta/llama-3.2-11b-vision-instruct`.
   - Includes `reasoning_content` fallback because some NVIDIA models return reasoning traces instead of plain content.

2. **Richer `ev status <project>`** (`src/ev/memory/status.py`, `src/ev/memory/store.py`, `src/ev/tools/status_tool.py`).
   - Phase inference via regex `(?i)\bphase\s+(\d+[A-Z]?)\b`.
   - Open issue count, open PR count, recent notes.
   - `MemoryStore` helpers: `count_open_issues`, `count_open_prs`, `recent_notes`, `list_active_projects`.

3. **`ev brief`** (`src/ev/tools/brief_tool.py`, `tests/test_brief_tool.py`).
   - Cross-project morning brief aggregating status for all active projects.

4. **Web research with citations** (`src/ev/tools/research_tool.py`, `tests/test_research_tool.py`).
   - DuckDuckGo HTML search via `httpx` (no API key).
   - NVIDIA LLM synthesizes answer with numbered citations.

5. **`ev work on <project> <task>`** (`src/ev/tools/work_tool.py`, `tests/test_work_tool.py`).
   - Tier 1 action. Spawns `claude code` CLI in the repo directory with prepared context.

6. **Tier 1 drafting tools** (`src/ev/tools/draft_tools.py`, `tests/test_draft_tools.py`).
   - `ev draft commit --project <name>` — drafts commit message from staged diff.
   - `ev draft pr --project <name>` — drafts PR title/body from branch diff vs `main`.
   - `ev draft reply --to <email> --subject <subject> --snippet <text>` — drafts email reply.

7. **Read-only Gmail/Calendar ingestion** (`src/ev/ingestion/gmail.py`, `src/ev/ingestion/calendar.py`, `src/ev/ingestion/google_auth.py`, `tests/test_google_ingestion.py`, `tests/test_calendar_prep.py`).
   - Gated by `EV_GOOGLE_ENABLED=true` and `assert_personal_only`.
   - Uses `google_auth_oauthlib` desktop app flow.
   - `GmailIngestion` blocks work domains (currently `financialsimplicity.com`) via `Blocklist`.
   - `CalendarIngestion` extracts `Deadline` rows from calendar events.

### Phase 3 features (all complete)

1. **Structured memory tables** (`src/ev/db/models.py`).
   - `Person`, `Obligation`, `Decision`.
   - Extended `Deadline` with `status`, `snooze_until`, `last_reminded`.

2. **`MemoryStore` structured CRUD** (`src/ev/memory/store.py`).
   - Idempotent upserts by `(source, source_id)` for `Deadline`, `Person`, `Obligation`, `Decision`.
   - `list_people`, `list_obligations`, `list_decisions`, `count_urgent_deadlines`, `mark_deadline_reminded`, `snooze_deadline`, `get_recent_emails`.

3. **Deadline watcher** (`src/ev/tools/deadline_watcher.py`).
   - Buckets deadlines into overdue / today / this-week / future.
   - Respects `snooze_until` and filters by project.

4. **Proactive alert loop** (`src/ev/server/api.py`).
   - FastAPI lifespan-managed background task.
   - Configurable via `EV_ALERT_INTERVAL_SEC`, `EV_ALERT_WINDOW_HOURS`, `EV_QUIET_START`, `EV_QUIET_END`, `EV_KILL_SWITCH`.

5. **`ev alerts` / `POST /alerts`** (`src/ev/tools/alerts_tool.py`).
   - Synthesizes urgent deadline digest.
   - Includes overdue obligations count.

6. **Pre-meeting prep** (`src/ev/tools/prep_tool.py`).
   - `ev prep meeting "<title>" --time <ISO>` and `ev prep today`.
   - Uses calendar event content, attendee people, recent emails, project status, and nearby obligations.
   - LLM generates agenda, talking points, open questions.

7. **People / obligations lookup** (`src/ev/tools/people_tool.py`, `src/ev/tools/obligations_tool.py`).
   - `ev people list` and `ev obligations list`.

8. **Phase 3 CLI/API commands**.
   - CLI: `ev deadlines list`, `ev people list`, `ev obligations list`, `ev alerts`, `ev prep meeting`, `ev prep today`.
   - API: `POST /deadlines`, `POST /people`, `POST /obligations`, `POST /alerts`, `POST /prep`.

### Live Google OAuth + sync completed today

- Created a Google Cloud **Desktop app** OAuth client for EV.
- Enabled **Gmail API** and **Calendar API**.
- Downloaded `credentials.json` to `C:/Users/point/projects/Hi-EV/secrets/credentials.json`.
- Added `EV_GOOGLE_ENABLED=true` and `EV_GOOGLE_CREDENTIALS_PATH=...` to `.env`.
- Ran `python scripts/google_auth.py`, completed browser consent flow, and saved `secrets/token.json`.
- Ran `python scripts/sync_google.py` successfully:
  - 20 Gmail messages ingested → 16 `Person` rows.
  - 30 calendar events ingested → 30 `Deadline` rows.
- Fixed `src/ev/google_auth.py` to store `token.json` in `secrets/` folder.
- Added local SQLite migration to add `status` and `snooze_until` columns to existing `deadlines` tables.

### Key bug fixes today

- **NVIDIA model EOL:** original default `meta/llama-3.3-70b-instruct` returned 410 Gone. Probed 16+ models with `scripts/test_nvidia_models.py` and selected `meta/llama-3.2-11b-vision-instruct` as the new default.
- **LLM reasoning traces:** added `reasoning_content` fallback in `LLMClient.complete()`.
- **Repo path missing on existing projects:** added `EV_ROBOCAD_PATH`, `EV_LEARNINGROBOTICS_PATH`, `EV_HIEV_PATH` to config and made `scripts/seed_demo.py` update existing `Project.repo_path` values.
- **Mixed-pair upsert bug:** fixed `tuple_(Ingest.source, Ingest.source_id).in_(...)` in `MemoryStore` and added regression test.
- **Missing schema in seed_demo:** added `Base.metadata.create_all`.
- **StatusTool KeyError:** added graceful fallback when project is missing.
- **`python -m evd` ran CLI instead of daemon:** fixed `src/evd.py` to import and call daemon `run()`.
- **CWD-relative DB issues:** set absolute SQLite path in `.env`.
- **Google token path:** changed `src/ev/google_auth.py` to save `token.json` in `secrets/` instead of a hidden sidecar.
- **Duplicate email people upsert:** `upsert_people` now deduplicates within a batch before inserting, preventing UNIQUE constraint errors when Gmail returns the same sender multiple times.
- **Naive/datetime-aware mismatch:** added UTC normalization in `DeadlineWatcherTool` and `PrepTool` so SQLite-stored naive datetimes compare safely with aware `datetime.now(UTC)`.

### Verification performed today

- `python -m pytest` → 82 passed, 1 skipped.
- `ruff check src tests scripts` → clean.
- Restarted EV daemon on `127.0.0.1:7345`.
- Seeded 30 GitHub records from RoboCAD, LearningRobotics, Hi-EV.
- Ran `python scripts/google_auth.py` and completed browser OAuth consent.
- Ran `python scripts/sync_google.py`: 20 Gmail → 16 people, 30 calendar events → 30 deadlines.
- API smoke tests:
  - `GET /health` → `{"status":"ok"}`.
  - `POST /status {"project":"Hi-EV"}` → phase + latest commit + deadline count.
  - `POST /brief` → works.
  - `POST /research {"query":"best local voice assistant stack 2026"}` → works with citations.
  - `POST /draft {"type":"reply",...}` → works.
  - `POST /draft {"type":"commit","project":"Hi-EV"}` → graceful "no staged changes".
  - `POST /deadlines`, `POST /people`, `POST /obligations`, `POST /alerts`, `POST /prep` → all work.
- CLI smoke tests:
  - `ev status Hi-EV` → works.
  - `ev brief` → works.
  - `ev research "LiveKit local voice assistant"` → works.
  - `ev draft commit --project Hi-EV` → graceful "no staged changes".
  - `ev draft reply --to ... --subject ... --snippet ...` → works.
  - `ev deadlines list` → works.
  - `ev people list` → works.
  - `ev obligations list` → works.
  - `ev alerts` → works.
  - `ev prep meeting "Happy birthday" --time 2026-11-19T00:00:00+00:00` → works.
  - `ev prep today` → works.

---

## 6. Voice / LiveKit research outcome

Voice is **deferred to Phase 5+**. LiveKit was researched. Options noted:
- Local LiveKit Plugins + Agents SDK (Python).
- RoomKit UI for browser/phone fallback.
- Tara for low-code voice agents.

Research doc: `docs/superpowers/research/2026-09-15-nvidia-api-livekit-voice.md`.

---

## 7. What is blocked / waiting on the user

**Nothing is currently blocked.** Gmail/Calendar live sync is working, Phase 3 is complete, and all tests pass.

Next optional user actions:
- Provide additional work domains to block in Gmail ingestion (currently only `financialsimplicity.com`).
- Confirm whether to proceed with Phase 4 (eval harness, T2 confirmation, automated CI diagnosis → draft PR, cost dashboard).

---

## 8. Permission tiers (current state)

| Tier | Policy | Examples |
|------|--------|----------|
| T0 | Always auto | memory/web/repo search, `ev status`, `ev brief`, `ev research`, `ev deadlines`, `ev people`, `ev obligations`, `ev alerts` |
| T1 | Auto, log, undoable | draft PR/commit/email, run tests, spawn Claude Code, `ev work on`, `ev calendar-prep`, `ev prep`, read-only Gmail/Calendar sync |
| T2 | Confirm exact payload | send email, push non-main branch, merge PR, post publicly (not yet implemented) |
| T3 | Hard-blocked | push to main, publish anything, spend money, touch work accounts or patent/IP (not yet fully enforced) |

Tier enforcement is currently mostly metadata; real T2 confirmation UI and T3 hard blocks are Phase 4 scope.

---

## 9. Default commands to verify health

When starting a new session, run these in order:

```bash
cd C:/Users/point/projects/Hi-EV
python -m pytest
ruff check src tests scripts
python scripts/seed_demo.py
python scripts/sync_google.py
python -m evd
```

Then in another shell:
```bash
curl -s http://127.0.0.1:7345/health | python -m json.tool
ev status Hi-EV
ev brief
ev deadlines list
ev people list
ev obligations list
ev alerts
ev prep today
ev research "current state of local LLM voice assistants 2026"
ev draft reply --to "test@example.com" --subject "Hello" --snippet "Want to meet?"
```

---

## 10. Phase 4 plan summary

Phase 4 is the next major milestone.

Main goals:
1. **Eval harness** — measure tool accuracy and LLM outputs against gold data.
2. **T2 confirmation UI** — real payload confirmation before any external write action.
3. **T3 hard-block enforcement** — prevent main-branch pushes, public publishes, spend, work-account access.
4. **Automated CI diagnosis → draft PR** — read test failures, reason, spawn work context, draft fix PR.
5. **Cost dashboard** — track LLM/cloud spend per project and per day.
6. Continue using live Gmail/Calendar sync for alerts and prep.

Next session should start by:
1. Confirming daemon still starts and tests pass.
2. Designing the T2 confirmation flow (CLI prompt + API endpoint + in-memory queue).
3. Building the eval harness for at least `status`, `brief`, `deadline_watcher`, and `prep` outputs.

---

## 11. Non-obvious context for a new session

- The default LLM **must** be `meta/llama-3.2-11b-vision-instruct`. Do not switch back to `meta/llama-3.3-70b-instruct`; it is EOL and returns 410 Gone.
- Use `scripts/test_nvidia_models.py` to probe which models work if the default ever breaks.
- The SQLite DB path is absolute in `.env`. If CLI behaves oddly, check `.env` and that `hiev.db` exists.
- `ev status` takes a positional argument (`ev status Hi-EV`), not `--project`.
- `ev draft commit` and `ev draft pr` require `--project`.
- `ev calendar prep` takes a positional time argument; `ev prep meeting` takes a positional title and optional `--time`.
- Daemon port is `7345`. If it fails to bind, kill the existing `python` process on that port.
- The project is local-first; the NVIDIA API is the only cloud dependency currently used. DuckDuckGo search is also cloud but no API key. Google APIs are now used for read-only Gmail/Calendar sync.
- Always preserve the personal-only boundary. If a connector or tool might touch work data, gate it behind `EV_PERSONAL_ONLY=true` (default) and a blocklist.
- User explicitly authorized use of `.env`, running tests, and running the daemon without asking each time.
- `token.json` from Google OAuth is already saved in `secrets/`. If it expires, run `python scripts/google_auth.py` again to refresh.
- Existing local SQLite databases created before Phase 3 may be missing `deadlines.status` and `deadlines.snooze_until`. A migration is included in the Phase 3 commit; if needed, run the alter statements manually.

---

## 12. Related memories

See [[project_hi-ev_2026-09-15]] for the compact project memory.
See [[project_learning_robotics_option_a_2026-08-13]] and RoboCAD memory files for the projects EV manages.
