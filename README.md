# EV — Personal AI Operating System

> **A local-first, privacy-first cognitive layer that runs on your personal RTX 5060 laptop, knows your projects, speaks first, and handles the boring parts while keeping you in control of the consequential ones.**

EV is not a chatbot. It is the persistent operating system for a single human — you — sitting above all your personal projects, tools, and data. When you open your laptop, EV is already there. It has read what changed overnight, tracked your deadlines, and is ready to work by voice or text.

---

## What EV is

- A **local daemon** that lives on your personal RTX 5060 laptop.
- A **memory system** that ingests and understands your GitHub repos, notes, calendar, emails, and project artifacts.
- A **proactive supervisor** that speaks first: morning briefs, deadline warnings, CI failures, meeting prep.
- An **action layer** that can draft PRs, run tests, open Claude Code with the right context, summarize threads, and schedule focus time — all within tiered safety rules.
- A **research agent** that searches the web, reads sources, and returns synthesized answers with citations.
- A **voice-first interface** for the "open laptop" experience: wake word or hotkey, ask, get a concise answer, keep working.

## What EV is not

- **Not AGI.** EV has no consciousness, no intuition in the human sense, and no judgment beyond pattern synthesis and calibrated recommendation. The final call is always yours.
- **Not work-integrated.** EV operates on your **personal** machines, accounts, and data only. It does not touch your employer laptop, work email, or work repos. This boundary is enforced in code, not in policy.
- **Not fully autonomous on consequential actions.** EV can draft, simulate, and execute reversible work automatically. It cannot push to `main`, send emails, post publicly, spend money, or publish anything without explicit human confirmation.
- **Not a cloud brain.** Your sensitive memory stays local. A tiny cloud relay only handles webhook ingress and phone fallback.

---

## Core principles

1. **Personal-only.** EV never ingests employer-owned data, work accounts, or work machines.
2. **Local-first.** Sensitive memory (repos, notes, emails, decisions) lives in a local Postgres on the RTX 5060 laptop.
3. **Tiered autonomy.** Every action has a permission tier. Lower tiers auto-execute; higher tiers require confirmation; the highest tier is hard-blocked.
4. **Provenance everywhere.** Every claim, citation, and recommendation must be traceable to a source.
5. **Audit everything.** Every action, tool call, decision, and model output is logged.
6. **Graceful degradation.** If the internet or cloud relay is down, the local daemon still answers questions about your local data.
7. **No hidden magic.** EV explains what it is doing, what it retrieved, and what it is about to do before it does it.

---

## Architecture (Option C: Hybrid Personal-First)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Personal RTX 5060 Laptop — The Primary Brain                                │
│  ─────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │ CLI daemon   │    │ Voice loop   │    │ System tray  │                │
│   │ `ev` command │    │ hotkey/wake  │    │ focus widget │                │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
│          │                   │                   │                         │
│          └───────────────────┴───────────────────┘                         │
│                              │                                               │
│                              ▼                                               │
│   ┌──────────────────────────────────────────────────────────────┐          │
│   │ EV Core (Python, asyncio)                                    │          │
│   │  • ingestion orchestrator                                    │          │
│   │  • memory router / retrieval                                 │          │
│   │  • reasoning router (fast / agent / deliberate)              │          │
│   │  • tool registry with tier enforcement                       │          │
│   │  • action audit + cost/latency tracking                       │          │
│   └──────────────────────┬───────────────────────────────────────┘          │
│                          │                                                   │
│          ┌───────────────┼───────────────┐                                 │
│          ▼               ▼               ▼                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────────┐                        │
│   │ Local    │    │ Local    │    │ Tool Registry │                        │
│   │ Postgres │    │ Redis    │    │  - git / gh   │                        │
│   │ +pgvector│    │ cache    │    │  - Claude Code│                        │
│   │          │    │          │    │  - pytest     │                        │
│   │ structured│    │ rate     │    │  - shell      │                        │
│   │ docs     │    │ limits   │    │  - browser    │                        │
│   │ episodic │    │          │    │  - calendar   │                        │
│   └──────────┘    └──────────┘    └──────────────┘                        │
│                                                                              │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ TLS/mTLS (webhooks + encrypted relay only)
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cloud Relay (cheap VPS / Fly / Render)                                    │
│  ─────────────────────────────────────────────────────────────────────────   │
│   • Webhook ingress for GitHub, Telegram, calendar                           │
│   • Job queue persistence when laptop sleeps                                 │
│   • Optional Telegram bot for phone access                                   │
│   • Encrypted backup of non-sensitive memory (opt-in, project-level)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

The **cloud relay is not the brain**. It is a durable mailbox and a phone bridge. The RTX 5060 laptop owns the memory, reasoning, and action loop.

---

## Data boundary contract

This is the most important rule in the repo. It exists because you have an employer, a provisional patent under India's absolute novelty standard, and a history of accidentally exposing a repo once.

### Allowed sources (personal only)

- Personal GitHub account and its repos (RoboCAD, LearningRobotics, NeuralQuant, Hi-EV, etc.).
- Local notes vault on the personal laptop (Obsidian/markdown folder).
- Personal Gmail account (read-only, action-item extraction).
- Personal Google Calendar (read-only, deadlines and prep).
- Personal Telegram/Slack accounts.
- Web pages, papers, changelogs, and public sources for research.

### Hard-blocked sources (never ingested, never acted upon)

- Employer laptop, employer email, employer Slack, employer accounts.
- Work repos, work code, work documents.
- Any account or path explicitly marked `work` in config.
- Any content that would compromise patent novelty or IP position.

### Enforcement

- A `personal_only` flag on every connector. If false, the connector refuses to initialize.
- A blocklist of work domains, handles, repo names, and machine identifiers.
- A classification step that tags every ingested item with `privacy_level`: `public`, `personal`, `sensitive`, `forbidden`.
- Any `forbidden` item is rejected and logged as a security event.
- A **kill switch**: one command revokes tokens, pauses automation, and switches EV to read-only.

---

## Permission tiers

Every tool and action in EV has a tier. The tier is enforced in code, not in a prompt.

| Tier | Name | Policy | Examples |
|------|------|--------|----------|
| **T0** | Read / research | Always auto-execute | Search memory, read repo, web search, read calendar, summarize file |
| **T1** | Reversible writes | Auto-execute, log loudly, easy undo | Draft commit message, create branch, draft PR, run tests, draft email, add calendar event, open Claude Code with context |
| **T2** | Consequential | Show exact payload, require explicit voice/text confirmation | Send email, push to non-main branch, merge PR, post on social, update public profile |
| **T3** | Never automated | Hard-blocked in code | Push to `main`, publish anything publicly, sign legal docs, spend money, disclose or publish patent/IP-related work, touch work accounts |

### Special rules

- A tool call whose parameters are derived from **freshly ingested untrusted text** (emails, GitHub issues, web pages) is automatically downgraded one tier.
- Any action touching `main` or `master` is T3 unless explicitly overridden in config for a specific repo and confirmed by a second factor.
- Voice commands can approve T2 actions. T3 actions can only be approved through the CLI with a typed confirmation string.

---

## Memory model

Three distinct stores in a single local Postgres database. One vector DB is not enough.

### 1. Structured facts

Rows with real types. Anything EV must get exactly right lives here.

- `projects` — name, current phase, goal, status, repo path, active flag
- `deadlines` — project, title, due date, priority, last reminded
- `people` — handle, relationship, project links, last contact
- `decisions` — project, decision text, reason, alternatives considered, date
- `tasks` — project, title, status, source URL, created/updated
- `obligations` — type, description, deadline, source

### 2. Document memory

Chunked, embedded, searchable documents.

- Repo files, READMEs, markdown notes, PDFs, transcripts, design docs, papers.
- Hybrid search: BM25 keyword + vector similarity + rerank.
- Provenance attached to every chunk.

### 3. Episodic log

Append-only record of everything that happened.

- Every user message, every tool call, every result, every decision.
- Enables *"why did I decide that?"* and *"what happened on Tuesday?"*

### Retrieval router

For each request, EV classifies intent and fetches only the relevant slices:

- Patent question → structured facts + IDF/prospectus docs
- Bug question → repo code + recent commits + CI logs
- Deadline question → structured deadlines + calendar
- Research question → web search + document memory

Retrieved context is capped and reranked. A 500K context window full of noise makes the model worse.

---

## Ingestion sources

| Source | What is ingested | Frequency | Privacy |
|--------|------------------|-----------|---------|
| GitHub (personal) | commits, PRs, issues, actions, releases, comments | webhook + hourly sync | personal |
| Notes vault | markdown files, PDFs, images (OCR later) | file-system watcher | personal/sensitive |
| Personal Gmail | incoming mail, action items, threads | 15-minute poll | sensitive |
| Personal Calendar | events, deadlines, attendees | webhook + hourly sync | sensitive |
| Laptop context | active window, open repo, idle state, last command | continuous | personal |
| Web | search results, browsed pages, RSS, changelogs | on demand | public |
| Telegram | messages to the bot | on demand | personal |

### Re-sync rule

Every ingested item carries `source_id` and a content hash. Re-syncs are idempotent.

---

## Interface layer

### CLI daemon

A global `ev` command available in any terminal:

```bash
ev brief                    # morning/now status brief
ev status RoboCAD           # what's the update on this project?
ev research "attention budgets in robot perception"  # web research with citations
ev work on "fix failing test in Phase 29"            # open Claude Code with context
ev remember "patent complete-spec due 21 Sep"        # one-command memory capture
ev draft reply --to recruiter@example.com            # draft an email in your voice
ev calendar prep 10:30                                   # prep packet for a meeting
ev why no "drop LCS mates"                           # trace a past decision
ev kill-switch                                         # pause all automation
```

### Voice loop

- Hotkey or wake word activates EV.
- Local Whisper for transcription.
- Intent classification.
- Response streamed; local TTS (Piper or similar).
- Conversational context is preserved across the session.

### System tray / desktop widget

- Shows current focus project.
- Shows next upcoming deadline.
- Mic status.
- One-click brief.

### Telegram fallback (via cloud relay)

- For when you are away from the laptop.
- Only receives summaries and can issue read-only or T1 commands (not T2/T3).

---

## Tool registry

Every tool is a typed Python function with:

- `name`, `description`, `input_schema`
- `tier`: T0/T1/T2/T3
- `dry_run()` method
- `run()` method
- `undo()` method (for T1)
- audit logging

### Example tools

- `memory_search(query)` — T0
- `web_search(query)` / `browse_page(url)` — T0
- `read_repo_file(path)` — T0
- `run_tests(repo, selector)` — T1
- `create_branch(repo, name)` — T1
- `draft_pr(repo, title, body)` — T1
- `spawn_claude_code(repo, task, context)` — T1
- `draft_email(to, subject, body)` — T1
- `send_email(draft_id)` — T2
- `push_branch(repo, branch)` — T2
- `merge_pr(repo, pr_number)` — T2
- `push_to_main(repo)` — T3 (blocked)
- `publish_anything(content)` — T3 (blocked)
- `access_work_account(account)` — T3 (blocked)

---

## Safety and security model

### Prompt injection defense

- All untrusted external content (emails, issues, web pages, Telegram messages) is wrapped in XML/JSON delimiters.
- The model is explicitly instructed that delimited text is data, not instruction.
- Any tool parameter derived from freshly ingested external text is downgraded one tier.
- A separate guard model/classifier flags suspicious instructions before action.

### Blast-radius controls

- Scoped tokens per connector. No long-lived admin credentials.
- Secrets live in a proper secrets manager or OS keyring, never plaintext `.env` alone.
- All network traffic from the local daemon uses mTLS to the cloud relay.
- Full audit log queryable through the CLI: `ev audit last 24h`.

### Kill switch

```bash
ev kill-switch
```

Instantly:
- Revokes all active API tokens.
- Pauses all automation and triggers.
- Switches EV to read-only mode.
- Sends a confirmation to the CLI and Telegram if configured.

---

## Phased roadmap

### Phase 1 — Foundation (1–2 weeks)

**Goal:** EV exists as a CLI daemon on the RTX 5060 laptop and can answer basic status questions about personal repos.

**Deliverables:**
1. Repo scaffold: `evd` daemon, FastAPI internal API, Postgres schema, CLI entrypoint.
2. GitHub personal repo ingestion (commits, issues, PRs, actions).
3. Local notes vault ingestion.
4. First memory query: `ev status <project>` returns a synthesized paragraph.
5. Voice skeleton: hotkey → Whisper → intent → LLM → TTS.
6. Basic audit log.

**Acceptance criteria:**
- `ev status RoboCAD` returns accurate one-paragraph status from repo history.
- Voice hotkey works and answers a simple question.
- All ingestion is idempotent.
- No work accounts or repos are ingested.

### Phase 2 — Presence + Status + Research (2–3 weeks)

**Goal:** EV feels like a real assistant: briefs, research, drafting, and Claude Code spawning.

**Deliverables:**
1. CLI daemon with hotkey/tray integration.
2. `ev brief` — morning/now status across all projects.
3. `ev status <project>` with full context: commits, open PRs, issues, recent decisions.
4. Read-only web research with citations: `ev research <query>`.
5. Tier 1 drafting: commit messages, PR descriptions, email drafts, meeting prep.
6. `ev work on <task>` — spawn Claude Code CLI with prepared context.
7. Personal Gmail + Calendar read-only ingestion (optional if risky).

**Acceptance criteria:**
- `ev brief` takes under 10 seconds and surfaces active projects, deadlines, and stale items.
- `ev research` returns a sourced summary with URLs.
- Drafts match your voice/style after a few examples.
- Claude Code spawns in the correct repo with the correct task context.

### Phase 3 — Structured Memory + Proactive Alerts (3–4 weeks)

**Goal:** EV knows deadlines, speaks first, and tracks your working context.

**Deliverables:**
1. Structured facts tables populated from ingestion + explicit capture.
2. Deadline watcher: `ev remember`, calendar extraction, recurring checks.
3. Morning brief and stale-project alerts.
4. Pre-meeting prep packets from calendar + attendee/project context.
5. Working-set model: EV detects which repo/window you are in.
6. One-command memory capture: `ev remember "X decided on Y because Z"`.

**Acceptance criteria:**
- EV warns about deadlines 14, 7, 3, and 1 day in advance.
- Pre-meeting brief is ready 15 minutes before each calendar event.
- Working-set model correctly identifies the active project 90%+ of the time.

### Phase 4 — Autonomy + Evaluations (4–6 weeks)

**Goal:** EV can safely execute more actions automatically and we can measure quality.

**Deliverables:**
1. Eval harness: 100–200 golden questions with known answers from your actual life and projects. ✅ Phase B seeded the harness with category-level golden cases; Phase 4 expands coverage.
2. Voice and CLI confirmation flow for T2 actions.
3. Automated T1 actions: CI failure → diagnosis → draft PR; stale issue → gentle nudge; test run → report delta.
4. Error recovery and retry logic.
5. Cost/latency dashboard per query.
6. Self-tuning: which summaries did you ignore? Which did you act on?

**Acceptance criteria:**
- Eval suite runs on every prompt change; hallucination and refusal rates tracked.
- T2 confirmation works by voice and CLI.
- A simulated CI failure produces a draft fix PR within 5 minutes.
- Cost per query is capped and visible.

### Phase C — Proactive Alerts + Persistent Context (3–4 weeks)

**Goal:** EV stops being purely reactive; it pushes alerts, remembers conversation threads, and surfaces what matters before it is too late.

**Deliverables:**
1. Server-initiated proactive alerts over WebSocket.
2. Persistent chat threads stored in local SQLite.
3. Morning brief scheduler.
4. Optional Telegram relay via cloud relay.

### Phase 5+ — Advanced features (later)

These are not blocked; they are sequenced after the core is reliable.

1. **Voice-first boot:** "Good morning, what are we working on today?"
2. **Predictive intervention:** move focus blocks, warn before patterns, cache fallbacks.
3. **Cross-project creative synthesis:** "Your drone morphology problem and your portfolio rebalancing problem both involve multi-objective search…"
4. **Consequence simulation:** "If you skip Phase 29 for the patent, here is the projected slip and risk."
5. **Self-improvement loop:** EV tracks its own accuracy and tunes retrieval/prompts.
6. **Phone access via Telegram:** lightweight remote queries and alerts.
7. **Local vision:** read screenshots, diagrams, sketches from your personal machine.

---

## Tech stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Core runtime | Python 3.12+ + asyncio + FastAPI | You know Python; RoboCAD stack synergy |
| Local DB | Postgres 16 + pgvector | Structured + vector in one database |
| Cache / queue | Redis | Rate limits, pub/sub, job state |
| LLM | Anthropic Claude (primary) + local Ollama (fallback/classification/embedding) | Frontier reasoning + local privacy for cheap tasks |
| Speech | faster-whisper (STT) + Piper / Coqui TTS (TTS) | Local voice, no cloud dependency |
| Voice activation | Porcupine / openWakeWord | Local wake word |
| IDE bridge | Claude Code CLI spawn + socket/stream | Reuse the tool you already use |
| Web research | DuckDuckGo / SearXNG + browser fetch | Avoid reliance on expensive X/Google APIs |
| Cloud relay | Fly.io / Render / small VPS | Webhooks + phone fallback only |
| Tray/CLI | `pynput` for hotkeys, `pystray` for tray | Cross-platform |

---

## First commands to implement

| Command | Phase | What it does |
|---------|-------|--------------|
| `ev status <project>` | 1 | Synthesized project status from repo + memory |
| `ev brief` | 2 | Cross-project now/morning brief |
| `ev research <query>` | 2 | Web research with citations |
| `ev work on <task>` | 2 | Spawn Claude Code with context |
| `ev remember <fact>` | 3 | One-command structured memory capture |
| `ev calendar prep <time>` | 3 | Meeting prep packet |
| `ev draft reply --to <email>` | 2 | Draft email in your voice |
| `ev run tests <project>` | 2/3 | Run test suite, report delta |
| `ev why no <decision>` | 3 | Trace a past decision |
| `ev kill-switch` | 1 | Pause all automation instantly |

---

## Why local-first

- Your repos, notes, emails, and decisions are a concentrated honeypot of personal IP.
- A cloud-first assistant would require trusting every provider with the full corpus.
- The RTX 5060 laptop is powerful enough to run Whisper, Ollama embeddings, and local classification.
- The "open laptop" experience only feels right if the brain is physically present on the machine you opened.

## Why not work-integrated

- Your employment contract has IP carve-outs for personal projects. EV must not blur that boundary.
- India's absolute novelty standard means any accidental publication of patent-relevant work can destroy your filing.
- An assistant that can publish, push, or forward content on your behalf is a genuine IP risk.
- Work context stays on work machines. EV stays on personal machines.

---

## Development norms

- Every change is tested with `pytest`.
- Every prompt change is validated against the eval harness.
- No API keys in source. Secrets in OS keyring or encrypted config.
- No work data in fixtures or test data.
- Commit messages follow conventional commits and end with the attribution line:
  `Co-Authored-By: Claude Code <noreply@anthropic.com>`

---

## Setup (Phase 1)

Hi-EV now defaults to **SQLite + sqlite-vec** so it runs without a system Postgres install. Postgres + pgvector remains an optional, fully supported upgrade path.

1. Install Python 3.12+.
2. Copy `.env.example` to `.env` and fill in at least:
   - `EV_NOTES_PATH`
   - `EV_GITHUB_TOKEN` (for live GitHub ingestion)
   - `EV_BLOCKED_HANDLES` and `EV_BLOCKED_DOMAINS` (JSON arrays of work handles/domains to block)
   - `EV_EMBEDDING_MODEL` (defaults to `all-MiniLM-L6-v2`)
   - `EV_DATABASE_URL` is optional; if omitted it defaults to a local SQLite file in `~/.hiev/hiev.db`.
3. Install the project:
   ```bash
   pip install -e ".[dev]"
   ```
4. Set up the local SQLite database with sqlite-vec:
   ```bash
   python scripts/setup_sqlite_vec.py
   ```
   This applies Alembic migrations and creates the sqlite-vec virtual table.
5. Verify the local embedding model and vector search:
   ```bash
   python scripts/check_embeddings.py
   python scripts/smoke_vector_search.py
   ```
6. Run tests:
   ```bash
   pytest
   ```
   Tests use an isolated in-memory SQLite database automatically.
7. Seed your local memory (optional, needs `EV_GITHUB_TOKEN`):
   ```bash
   python scripts/seed_demo.py
   ```
8. Run the daemon:
   ```bash
   python -m evd
   # or
   uvicorn ev.server.api:app --host 127.0.0.1 --port 7345
   ```
9. Open the voice/HUD web client:
   ```bash
   cd web
   npm install
   npm run dev
   ```
   Then visit `http://localhost:5173` and speak or type a command such as *"status RoboCAD"*.
10. Query status from the CLI or API:
    ```bash
    ev status RoboCAD
    ```
    Or via the API:
    ```bash
    curl -X POST http://127.0.0.1:7345/status -H "Content-Type: application/json" -d '{"project":"RoboCAD"}'
    ```

### Optional: Postgres + pgvector

If you prefer Postgres, install Postgres 16 with pgvector and set `EV_DATABASE_URL`:
- **Windows:** [EDB Postgres installer](https://www.postgresql.org/download/windows/) or `winget install PostgreSQL.PostgreSQL`.
- **WSL2 / Linux:** `sudo apt install postgresql postgresql-contrib pgvector`.

```bash
python scripts/setup_postgres.py
alembic upgrade head
```

The same Alembic migrations and vector helpers work on both backends.

---

## Status

**Phase 1 — Foundation implemented.**

The local daemon scaffold, personal-only security boundary with a config-driven blocklist, GitHub + notes + Gmail + Calendar ingestion, browser voice/HUD shell, and the first `ev status <project>` command are in place and tested.

**Phase A — Ambient Ingestion + Semantic Memory implemented.** Document chunking, local `all-MiniLM-L6-v2` embeddings, sqlite-vec hybrid search, the `ev remember` command, memory/remember API + WebSocket intents, and a background daemon ingestion scheduler are complete and pushed. `StatusTool`, `PrepTool`, and `ResearchTool` ground their answers in document memory.

**Phase B — Reasoning Router + Eval Harness + Streaming UI implemented.** The reasoning router, source-trust propagation, guard model, streaming LLM fast path, backend stop/abort control, eval harness, and extraordinary frontend streaming UI are complete and pushed to `origin/main`. Full test suite: **181 passed, 1 skipped**. The next phase is **Phase C — Proactive Alerts + Persistent Context**.

---

## License

Personal use only. EV is not a product. It is your own infrastructure.
