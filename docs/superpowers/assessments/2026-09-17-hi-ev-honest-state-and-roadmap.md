# Hi-EV — Honest State Assessment and Roadmap to the Full Vision

> **Date:** 2026-10-04 (updated)
> **Commit area:** Phase G Tauri wrapper skeleton + quiet-hours fix
> **Tests:** 253 passed, 1 skipped
> **Ruff:** clean
> **Frontend build:** clean
> **Tauri build:** `cargo check`/`cargo clippy` clean; Windows MSI produced
> **Status:** Web/Voice/HUD MVP complete. Phases A–F complete and pushed to `origin/main`. Phase G is in progress: Tauri skeleton complete; user-approved end-to-end launch roadmap defined (G1–G6).

---

## 1. Executive summary

Hi-EV has gone from a README vision to a working local daemon with a browser-native voice/HUD face and a desktop presence entry point. The core is real: FastAPI daemon, SQLAlchemy memory, tiered tool registry, OpenJarvis-style plugin registry/ABCs, skills runtime, local voice pipeline, personal-only security boundary, GitHub/notes/Gmail/Calendar ingestion, safe code sandbox, eval runner, encrypted secrets vault, read-only auto-updater, and a React/Three.js frontend that can hear you and answer via WebSocket.

That is a genuine milestone. But against the full vision — *ambient executive layer that wakes up before you do, knows every project and commitment, and acts autonomously within safe tiers* — we are now at roughly **Phase 5 of 6+**.

This document is an honest inventory of what works, what is half-built, what is missing, and the shortest credible path from here to the vision.

---

## 2. What is real today

### 2.1 Backend daemon
| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI daemon (`python -m evd`) | ✅ Working | Runs on `127.0.0.1:7345`, health endpoint, CORS for `localhost:5173`. |
| Async SQLAlchemy + SQLite/Postgres | ✅ Working | Default is SQLite + sqlite-vec (`~/.hiev/hiev.db`); Postgres + pgvector optional via `EV_DATABASE_URL`. Tests use in-memory SQLite. |
| Schema migrations (Alembic) | ✅ Working | Base migration `aacdc9089a90` is frozen. New `document_chunks` migration `e65cfe42f3a6` added. Migration discipline documented in `docs/development/migrations.md`. |
| Lifespan + alert loop | ✅ Working | Background loop scans deadlines and pushes `type: alert` events to all active WebSockets; morning brief scheduler fires at configured time. |
| Persistent chat threads | ✅ Working | `ChatThread`/`ChatTurn` models, REST CRUD, resume across reconnects, 20-turn rolling window. |
| Settings / `.env` | ✅ Working | Pydantic settings, env-file driven, personal-only flag enforced, Phase D/E/F flags added. |
| Encrypted secrets vault | ✅ Working | `ev.secrets` stores encrypted key/value pairs; key from OS keyring or `EV_MASTER_PASSWORD`; loaded before pydantic reads env. |
| Read-only auto-updater | ✅ Working | `ev.updater` compares against GitHub releases and prints installer URL; never downloads/runs code without user confirmation. |

### 2.2 Memory / structured facts
| Component | Status | Notes |
|-----------|--------|-------|
| `Project`, `Ingest`, `Deadline`, `Person`, `Obligation`, `Decision`, `Event` models | ✅ Real | Upsert helpers exist, idempotency by `(source, source_id)`. |
| `MemoryStore` CRUD | ✅ Real | Covers ingestion, deadlines, people, obligations, decisions, events. |
| Vector / semantic document memory | ✅ Working | `DocumentChunk` model, sqlite-vec vector table, local embeddings, chunking pipeline, hybrid search, `memory_search` tool, and `ev remember` command are implemented. |
| Episodic log queryability | ⚠️ Partial | `Event` table exists; chat turns are persisted, but no `ev why` retrieval tool or reasoning over history. |
| Cross-project synthesis | ⚠️ Partial | `brief` aggregates; true synthesis across people/obligations/decisions is hand-rolled, not systematic. |
| Preference memory | ❌ Missing | No tracking of ignored reminders, preferred answer length, or voice speed. |

### 2.3 Ingestion
| Source | Status | Notes |
|--------|--------|-------|
| GitHub personal repos | ✅ Working | Commits, issues, PRs fetched, blocklist enforced. |
| Notes vault (markdown) | ✅ Working | File watcher not implemented — manual ingestion only. |
| Gmail | ✅ Working | Read-only, extracts people, sensitive privacy level. |
| Google Calendar | ✅ Working | Extracts events, deadlines, people, obligations. |
| Web research | ✅ Working | DuckDuckGo + LLM synthesis with citations, Redis cache optional. |
| Active window / laptop context | ❌ Missing | No working-set detection. |
| RSS / changelogs | ❌ Missing | Not implemented. |
| Telegram relay | ⚠️ Skeleton | `src/ev/server/telegram.py` exists; disabled by default. |
| Webhook ingress | ❌ Missing | No cloud relay, no GitHub webhooks. |
| Idempotency | ✅ Real | Content-hash + `(source, source_id)` upserts. |

### 2.4 Tools / action layer
| Tool | Tier | Status |
|------|------|--------|
| `status` | T0 | ✅ Works via CLI, REST, WebSocket. |
| `brief` | T0 | ✅ Works. |
| `research` | T0 | ✅ Works, cached. |
| `deadline_watcher` / `alerts` | T0 | ✅ Works; alert loop pushes to WebSocket. |
| `people` | T0 | ✅ Lists. |
| `obligations` | T0 | ✅ Lists. |
| `prep` / `calendar_prep` | T0 | ✅ Works, prep packet from calendar + context. |
| `draft_commit` | T2 | ✅ Works; requires confirmation in web/voice, `--yes` in CLI. |
| `draft_pr` | T2 | ✅ Works; requires confirmation in web/voice, `--yes` in CLI. |
| `draft_reply` | T2 | ✅ Works; requires confirmation in web/voice, `--yes` in CLI. |
| `work_on` (spawn Claude Code) | T2 | ✅ Works; requires confirmation in web/voice, `--yes` in CLI. Process spawn still pipes context into stdin. |
| `send_email`, `push_branch`, `merge_pr` | T2/T3 | ❌ Not implemented. |
| `remember` explicit capture | T1 | ✅ `ev remember "..."` and `POST /remember` implemented; stores as `DocumentChunk`. |
| `kill-switch` | T3 guard | ❌ Not implemented. |
| Tier enforcement in WebSocket | ✅ | T2 pauses for `confirm`/`confirm_response`; T3 hard-blocked in web/voice. |
| Sandbox tool (code execution) | T2 | ✅ `ev.sandbox` + `SandboxTool` shipped in Phase F; tier-2 confirmation required. |
| Skills runtime | ✅ | `ev.skills` discovers `SKILL.md` files and exposes each as a tool via `SkillTool`. |

### 2.5 LLM / reasoning
| Capability | Status | Notes |
|------------|--------|-------|
| Provider-agnostic client (NVIDIA/OpenAI/Anthropic) | ✅ Working | OpenAI-compatible completions + streaming SSE. |
| Intent classification | ✅ Working | JSON-only prompt, routes to tools. |
| Chat / direct answer fallback | ✅ Working | General conversation via LLM; fast path streams. |
| Streaming responses | ✅ Working | `LLMClient.complete_stream()` yields deltas; WebSocket fast-chat path streams word-by-word with stop control. |
| Reasoning router | ✅ Working | Heuristic fast/agent/deliberate classifier with optional LLM fallback; emits `phase: route:<path>`. |
| Eval harness / golden questions | ✅ Working | `ev.eval` suite runner with checks, JSON/YAML loader, and `ev eval run [suite_dir]` CLI. |
| Prompt injection guard | ✅ Working | `Guard.check()` with SAFE/CAUTION/BLOCKED; runs before routing; source-trust tier downgrades for untrusted content. |

### 2.6 Voice / HUD frontend
| Component | Status | Notes |
|-----------|--------|-------|
| Vite + React + TypeScript scaffold | ✅ Working | Builds cleanly. |
| Three.js reactor scene | ✅ Working | Core + particles, shader ring; maps streaming phase to color/spin. |
| HUD components | ✅ Working | Boot, Ignition, Hud, Diagnostics, Suggestions, Chat panel, Threads panel, Alerts panel. |
| WebSocket bridge | ✅ Working | Auto-reconnect, delta/done/error/phase/confirm/focus/alert events. |
| Browser SpeechRecognition STT | ✅ Working | Push-to-talk via Space; continuous wake-word listener for "hey ev". |
| Browser speechSynthesis TTS | ✅ Working | Sentence queue, barge-in. |
| Local STT (faster-whisper) | ✅ Working | `ev.voice` with `faster_whisper` backend shipped in Phase F; mock backend for CI. |
| Local TTS (Kokoro/pyttsx3) | ✅ Working | `ev.voice` with `kokoro` and `pyttsx3` backends shipped in Phase F; mock backend for CI. |
| Persistent chat history | ✅ Working | Chat threads persist across reconnects; thread CRUD in UI. |
| Proactive server→client alerts | ✅ Working | `_alert_loop` pushes `type: alert` to all WebSockets. |
| HTML blades / model-authored panels | ❌ Missing | Text responses only. |
| System tray / desktop widget | ✅ Working | `scripts/desktop_presence.py` is the single entry point: daemon launch, global hotkey, tray widget, voice loop. |

### 2.7 Security / safety
| Component | Status | Notes |
|-----------|--------|-------|
| `personal_only` guard | ✅ Working | Asserted on ingestion sources. |
| Work blocklist (handles + domains) | ✅ Working | Config-driven via `EV_BLOCKED_HANDLES` / `EV_BLOCKED_DOMAINS` in `.env`. |
| Privacy levels (`public/personal/sensitive/forbidden`) | ⚠️ Partial | Field exists; no `forbidden` rejection pipeline or audit event. |
| Tiered tool enforcement | ✅ Working | T0 auto, T1 reversible auto, T2 paused for confirmation, T3 hard-blocked in web/voice. CLI T2 requires `--yes`/interactive confirm. |
| Source-trust tier downgrade | ✅ Working | Untrusted ingested content auto-downgrades effective tool tier. |
| Kill switch | ❌ Missing | Not implemented. |
| Audit log queryable | ⚠️ Partial | Events logged; no `ev audit` command. |
| Secrets in OS keyring / encrypted vault | ✅ Working | `ev.secrets` with `cryptography.fernet`; OS keyring via `keyring`, password fallback via `EV_MASTER_PASSWORD`. |
| mTLS to cloud relay | ❌ N/A | No relay yet. |

---

## 3. Maturity against the 10 superpowers

| # | Superpower | Maturity | Honest verdict |
|---|------------|----------|----------------|
| 1 | Ambient awareness | 7/10 | Background ingestion scheduler polls notes, GitHub, Gmail, Calendar; long-form content is chunked, embedded, and indexed. File-system watcher and webhook ingress remain future work. |
| 2 | Voice-first command | 8/10 | Browser voice loop works end-to-end; desktop voice loop via `scripts/desktop_presence.py` uses local faster-whisper/Kokoro/pyttsx3; wake word still browser-based. |
| 3 | Project memory | 8/10 | Structured facts + document chunks + hybrid search; router/eval measure retrieval quality. No deep dossier reasoning yet. |
| 4 | Autonomous execution | 7/10 | Tiered enforcement works: T0/T1 auto-run, T2 confirms in web/voice/CLI, T3 hard-blocked. Sandbox tool and skills runtime shipped. |
| 5 | Cross-project synthesis | 6/10 | Memory snippets surface across tools; brief aggregates. True synthesis across commitments/people is still hand-rolled. |
| 6 | Proactive alerts | 7/10 | WebSocket push alerts, morning brief scheduler, Telegram skeleton; no phone/email fallback yet. |
| 7 | Conversation continuity | 8/10 | Persistent chat threads across reconnects and reloads; no preference learning yet. |
| 8 | Tool-authoring loop | 2/10 | Skills runtime lets prompt-based capabilities be added via `SKILL.md`; self-authoring Python tools not yet implemented. |
| 9 | Holographic HUD | 4/10 | Visual shell + chat/alerts/thread panels; still text-only, no model-authored blades or gaze/click UI. |
| 10 | Local, private, inspectable | 7/10 | Runs local, memory local, provenance attached to ingest, guard + tier enforcement, encrypted secrets vault. No `ev why`, no kill switch, no audit query UI, no structured observability. |

**Average maturity: ~6.4/10.**

Phases A–F closed the core operating-system layer and added plugin extensibility, local voice, sandboxed code execution, evals, encrypted secrets, and an auto-updater. EV is now ambient, measurable, proactive, persistent, safely autonomous, and extensible. Phase G will wrap it in a native desktop shell and add cloud ingress/observability.

---

## 4. The hard gaps (what separates MVP from vision)

### Gap 1: File-system watcher and webhook ingress
Ingestion is still primarily scheduler-driven. The vision requires EV to *watch* sources continuously: GitHub webhooks, file-system watcher on notes, RSS feeds. Without this, EV is ambient-but-polling rather than truly event-driven.

### Gap 2: Document / semantic memory — LARGELY CLOSED
`DocumentChunk` + sqlite-vec + hybrid search + grounded tools now answer "what did the README say about actuator sizing?" from indexed documents. What remains is deeper reasoning over documents (summaries, compare/contrast, trend detection), a true reranker, and cross-document synthesis.

### Gap 3: Reasoning router — CLOSED
`ev.reasoning.router` now classifies requests into fast/agent/deliberate paths and is integrated into the WebSocket chat path. Cost/latency budgets and deeper deliberation loops remain future polish.

### Gap 4: Eval harness — CLOSED
`ev.eval` provides a reusable eval runner with checks, JSON/YAML loaders, and CLI reporting. Golden datasets and skill eval harness remain Phase G work.

### Gap 5: Proactive loop — CLOSED
The alert loop now pushes `type: alert` events to all active WebSockets. A morning brief scheduler fires at the configured time. Telegram relay skeleton is wired but disabled by default; phone/email fallback remains future work.

### Gap 6: T2/T3 confirmation — CLOSED
T2 actions pause for a `type: confirm` message and wait for `confirm_response` in WebSocket, voice, and CLI. T3 actions are hard-blocked in web/voice. The guard downgrades tier for untrusted sources.

### Gap 7: Persistent conversation — CLOSED; preference memory remains
Chat threads persist across reconnects and page reloads. EV does not yet learn from ignored reminders or preferred answer length/voice speed.

### Gap 8: Desktop presence — CLOSED
`scripts/desktop_presence.py` is the single installable entry point: it launches the daemon, global hotkey, system tray, and (when voice is enabled) a local voice loop.

### Gap 9: Local STT/TTS — CLOSED
`ev.voice` ships with mock, faster-whisper, kokoro, and pyttsx3 backends selected by config. The browser still provides a zero-install fallback, but the local pipeline works offline.

### Gap 10: Tool self-authoring, structured observability, cloud relay
EV cannot yet propose and grow its own Python tools, trace cost/latency/audit in one place, or receive webhooks from a cloud relay. These are the core of Phase G.

---

## 5. Roadmap from today to the vision

We propose **six phases**, each with a clear deliverable and acceptance criteria. The phases are ordered by dependency and user-facing impact.

### Phase A — Ambient Ingestion + Semantic Memory ✅ COMPLETE (`40aaa2b`, 2026-09-17)
**Goal:** EV keeps itself up to date and can answer questions over documents, not just structured rows.

**Prep sprint (completed):**
- Default database switched to SQLite + sqlite-vec; Postgres + pgvector optional.
- `DocumentChunk` model, sqlite-vec vector table, and local embedding model wired.
- Config-driven blocklist and migration discipline in place.

**Deliverables (completed):**
1. Continuous ingestion scheduler (`src/ev/server/scheduler.py`):
   - Periodic poll loop wired into FastAPI lifespan.
   - Runs `NotesIngestion`, `GitHubIngestion` (when `EV_GITHUB_REPOS` configured), `GmailIngestion` + `CalendarIngestion` (when `EV_GOOGLE_ENABLED=true`).
   - Long-form records are chunked and indexed into sqlite-vec automatically.
   - File-system watcher, RSS/changelog watcher, and GitHub webhooks remain future work.
2. Document memory pipeline:
   - Chunk markdown, notes, emails, calendar details, web pages via `src/ev/memory/chunks.py`.
   - Local embeddings via `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim).
   - sqlite-vec vector store + SQL keyword overlap + recency/source-type rerank.
3. Memory query tool:
   - `MemoryTool` / `RememberTool` in `src/ev/tools/memory_tool.py`.
   - `POST /memory` and `POST /remember` API endpoints.
   - WebSocket intents: `memory`, `search_memory`, `find_memory`, `recall`, `remember`, `save_memory`.
   - `StatusTool`, `PrepTool`, `ResearchTool` retrieve and inject document-memory snippets.
4. `ev remember "..."` command → stores explicit facts as `DocumentChunk` rows.

**Verification:**
- `python -m pytest` → 115 passed, 1 skipped.
- `python scripts/smoke_semantic_memory.py` passes end-to-end.
- `ruff check .` clean.

**What remains for later:** file-system watcher, RSS/changelog feeds, true cross-document synthesis, dedicated reranker model.

### Phase B — Reasoning Router + Eval Harness ✅ COMPLETE (`beb47fe`, 2026-09-19)
**Goal:** EV chooses the right reasoning depth, and we can measure quality.

**Deliverables:**
1. Router (`ev.reasoning.router`):
   - Fast path: retrieval → answer (cheap, <2s).
   - Agent path: multi-step tool loop for complex tasks.
   - Deliberate path: planning + reflection for high-stakes decisions.
2. Streaming completions in `LLMClient` and WebSocket.
3. Eval harness:
   - 100+ golden questions with ground-truth answers from real memory.
   - Metrics: hallucination rate, refusal rate, latency, cost.
   - Runs on every prompt/model change.
4. Guard model / prompt-injection classifier.

**Acceptance criteria:**
- ✅ `pytest tests/eval/` runs and produces a score report.
- ✅ A prompt change that lowers eval score is caught before merge.
- ✅ WebSocket responses stream word-by-word.

### Phase C — Proactive Alerts + Persistent Context ✅ COMPLETE (`dff10c3`, 2026-09-22)
**Goal:** EV speaks first and remembers the conversation.

**Deliverables:**
1. Push alerts over WebSocket:
   - Deadline watcher emits `alert` events to all connected clients.
   - Frontend HUD shows alert blades.
2. Persistent chat threads:
   - `ChatThread` table, resume across reconnects.
   - Preference capture (ignored reminders, answer length, voice speed).
3. Morning brief scheduler:
   - Runs at configured wake time.
   - Pushes brief to WebSocket / tray / optional Telegram.
4. Telegram bot via cloud relay (optional opt-in).

**Acceptance criteria:**
- ✅ With browser open, an urgent deadline produces a visible HUD alert within one alert interval.
- ✅ Closing and reopening the browser resumes the last conversation.
- ✅ `ev brief` can be scheduled and delivered automatically.

### Phase D — Safe Autonomy + Desktop Presence ✅ COMPLETE (`92ff90d`, 2026-09-22; live smoke test passed)
**Goal:** EV can act on T1 reliably and confirm T2 safely; it lives outside the browser.

**Deliverables:**
1. T2 confirmation flow:
   - Voice/CLI exact-phrase confirmation.
   - Payload preview before execution.
   - Timeout and revocation.
2. T3 hard blocks:
   - Push to `main`, public publish, spend money, work accounts → refused in code.
3. New T1 tools:
   - `run_tests`, `create_branch`, `schedule_focus_time`.
4. System tray / desktop widget:
   - `pynput` global hotkey.
   - `pystray` icon with focus project, next deadline, mic status.
5. Local wake word (Porcupine WASM / openWakeWord).

**Acceptance criteria:**
- ✅ A T2 tool request stops at `type: confirm` and shows exact payload; confirming runs the action, denying cancels it.
- ✅ Push to `main`/destructive intents are refused regardless of prompt or voice command.
- ✅ Hotkey (`Ctrl+Alt+E`) activates EV from any app; browser wake word ("hey ev") triggers listening.

### Phase E — Launch MVP (Local Installer + Setup Wizard) ✅ COMPLETE (commit `f304bb5` area through `02781e2`, 2026-10-02)
**Goal:** Ship a launch-ready, local-only Hi-EV that a non-technical user can download, install, and run on Windows without writing `.env` files or opening a terminal.

**Deliverables:**
- Unified desktop entry point `scripts/desktop_presence.py`.
- First-run setup wizard backend (`GET /setup`, `POST /setup`) and frontend `SetupWizard.tsx`.
- Graceful missing-LLM-key fallback in chat handler.
- Windows installer build script (`scripts/build_installer.py`) producing a portable `dist/Hi-EV.exe`.
- Documentation and memory files updated.

**Acceptance criteria:**
- ✅ `python scripts/build_installer.py` produces a runnable `dist/Hi-EV.exe`.
- ✅ Running `Hi-EV.exe` on a clean Windows machine opens the browser to the setup wizard if `.env` is missing.
- ✅ Setup wizard writes `.env`, restarts the daemon, and the HUD becomes usable.
- ✅ Without an LLM key, the HUD shows a friendly read-only/fallback message instead of crashing.
- ✅ Tray icon, global hotkey (`Ctrl+Alt+E`), and wake word still work.
- ✅ `python -m pytest` passes (197+ passed, 1 skipped).
- ✅ `ruff check .` clean.
- ✅ `cd web && npm run build` clean.
- ✅ README and memory files updated.

### Phase F — Plugin Architecture, Skills, Voice, Sandbox, Eval, Secrets, Auto-Updater ✅ COMPLETE (`02781e2`, 2026-10-03)
**Goal:** Turn Hi-EV from a hardcoded tool list into an extensible personal AI OS with local voice, safe code execution, and encrypted secrets.

**Deliverables:**
- OpenJarvis-style plugin registry/ABCs (`ev.core.registry`, `ev.core.component`, `ev.core.discovery`).
- All existing tools converted to `@register("tool", ...)` decorators.
- Skills runtime (`ev.skills`) loading `SKILL.md` files as tools.
- Local voice pipeline (`ev.voice`) with mock/faster-whisper/kokoro/pyttsx3 backends and `VoiceManager`.
- Desktop presence voice loop: hotkey triggers record → transcribe → `POST /voice/chat` → synthesize.
- Safe code sandbox (`ev.sandbox` + `SandboxTool`) with AST whitelist and subprocess isolation.
- Eval runner abstraction (`ev.eval`) with checks, JSON/YAML loader, and CLI.
- Encrypted secrets vault (`ev.secrets`) backed by `cryptography.fernet` and OS keyring.
- Read-only auto-updater (`ev.updater` + `ev update`).
- Single `scripts/desktop_presence.py` entry point for daemon, hotkey, tray, and voice.

**Verification:**
- `python -m pytest` → **253 passed, 1 skipped**.
- `ruff check .` → clean.
- `cd web && npm run build` → clean.
- Commit `02781e2` pushed to `origin/main`.

### Phase G — Tauri Desktop Wrapper, File-System Watcher, Voice, Skill Evals, Safety (active, launch-blocking)
**Goal:** Wrap EV in a polished native desktop shell, make ingestion event-driven, harden voice end-to-end, measure skill quality, and close the remaining safety gaps so a non-technical user can install and run Hi-EV on Windows.

**Deliverables:**
1. ✅ **G0** Tauri desktop wrapper skeleton:
   - Native window loading `web/dist`, system tray, global shortcut, daemon manager.
   - Windows MSI installer produced; macOS/Linux targets configured.
2. ✅ **G1** Tauri Launch Polish complete:
   - Real icons, setup-wizard Python check, configurable shortcut, daemon crash recovery, tray update item, quit cleanup.
   - Tauri artifact smoke test (`scripts/smoke_tauri.py`); clean-VM MSI smoke test remains manual.
3. 🚧 **G2** File-System Watcher (next stream):
   - Watch `notes_path` and active project directories.
   - Incremental ingestion and re-indexing with debounce/idempotency.
4. **G3** Voice End-to-End:
   - Local voice (`faster-whisper` + Kokoro/pyttsx3) works through Tauri shortcut and HUD.
   - Browser SpeechRecognition fallback.
   - Voice settings in setup wizard; voice smoke test.
5. **G4** Skill Eval Golden Datasets:
   - Golden questions for built-in skills.
   - Per-skill pass/fail report with latency.
6. **G5** Security, Safety & Kill Switch:
   - Kill switch pauses loops and T1/T2 actions.
   - Queryable audit log.
   - Personal-only boundary review and setup blocklist step.
7. **G6** Final Integration & Launch Test Sweep:
   - End-to-end smoke tests through the MSI.
   - Performance benchmarks and clean uninstall verification.
   - Version bump and changelog.

**Deferred to v1.1 / Phase H:** macOS/Linux installers, cloud relay/webhook ingress, observability/cost tracing (`ev why`), LiveKit optional cloud voice, real OpenJarvis code/skill integration, tool self-authoring loop, global wake word outside browser, desktop screenshot ingestion.

**Acceptance criteria:**
- Native desktop app installs and runs on Windows without a browser tab.
- Adding a file to the notes vault is reflected in memory within minutes.
- Voice works end-to-end (local or browser fallback).
- Skill eval suite produces pass/fail reports with per-skill latency.
- Kill switch hard-pauses autonomous actions.
- Full test suite passes; ruff clean; frontend build clean; Tauri build clean.

---

## 6. Technical debt to pay down soon

1. **Migration base revision drift — RESOLVED.** Migration discipline is now documented in `docs/development/migrations.md`; base revision `aacdc9089a90` is frozen. Chat-thread and trusted-source migrations added.
2. **Work blocklist is hardcoded — RESOLVED.** Blocklist is config-driven via `EV_BLOCKED_HANDLES` / `EV_BLOCKED_DOMAINS`.
3. **Claude Code spawn is fragile.** `work_on` pipes context into stdin of `claude code`; the CLI likely ignores it. Move to a context file or dedicated launch protocol.
4. **Redis assumed but optional.** Research tool degrades gracefully, but other features may assume Redis. Make Redis optional everywhere or document it as required.
5. **Secrets in `.env` — RESOLVED.** `ev.secrets` stores encrypted key/value pairs; OS keyring via `keyring`, password fallback via `EV_MASTER_PASSWORD`.
6. **No structured logging / observability — STILL OPEN.** Add OpenTelemetry or structured logs for cost/latency/audit tracing in Phase G.
7. **Desktop presence not packaged — RESOLVED.** `scripts/desktop_presence.py` is the single entry point for daemon launch, hotkey, tray, and voice loop.

---

## 7. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Prompt drift degrades intent classification | High | Phase B eval harness + guard model. |
| Ingestion loops hit API rate limits | Medium | Backoff, idempotency, jitter, local caching. |
| Document memory bloats local DB | Medium | Chunk size limits, lazy embedding, archive old chunks. |
| T2 confirmation spoofed by prompt injection | High | Guard model, exact-phrase confirmation, tier downgrade for untrusted sources. |
| Patent/IP leakage through email/web ingestion | High | Privacy classifier, forbidden tag, blocklist, kill switch, personal-only enforcement. |
| Local LLM too slow for real-time voice | Medium | Keep cloud STT/TTS as fallback; classify locally, synthesize locally when fast enough. |
| Frontend build breaks on Node version drift | Low | Pin Node version, CI build check. |
| Plugin registry accidentally loads unsafe modules | Medium | Discovery only imports known `ev.*` packages; skills are prompt-based and sandboxed. |
| Auto-updater social-engineering risk | Medium | Read-only comparator; never downloads or runs installers without explicit user confirmation. |

---

## 8. What to build next (recommended immediate sprint)

Phases A–F and Phase G1 are complete. The user-approved launch roadmap is **Phase G1–G6**. The highest-leverage next work is **G2 — File-System Watcher** so EV feels ambient: when you add or edit a note or project file, EV updates its memory within minutes instead of waiting for the next scheduler poll.

**Sprint goal:** Add a `watchdog`-based file-system watcher that incrementally ingests changes from the notes vault and active project directories, with debounce/idempotency and full test coverage.

**Tasks:**
1. Create `ev.ingestion.watcher` using `watchdog` to watch `settings.notes_path` and configured project paths.
2. Debounce and coalesce events (e.g., 2-second quiet period).
3. Incrementally re-run ingestion and re-index `DocumentChunk` rows only for changed paths.
4. Hook watcher into FastAPI lifespan (start on boot, stop on shutdown).
5. Add watcher tests for create, modify, and delete events.

**Acceptance criteria:**
- Adding a `.md` file to the notes vault is queryable via memory search within 2 minutes.
- Deleting a note removes its chunks from the vector store.
- Full test suite still passes; ruff clean; frontend build clean; Tauri build clean.

---

## 9. Metrics to track

| Metric | Target by end of Phase A | How to measure |
|--------|--------------------------|----------------|
| Ingestion freshness | <15 minutes for notes, <1 hour for GitHub | Scheduler intervals + last ingest timestamp. |
| Status answer accuracy | ≥80% on golden status questions | Eval harness (target for Phase B). |
| Research citation correctness | ≥85% citations point to real source | Manual spot-check + eval (target for Phase B). |
| Intent classification accuracy | ≥90% | Labeled transcript test set. |
| End-to-end voice latency | <5s from speech stop to first delta | Smoke test timing. |
| WebSocket uptime | 99.9% local | Smoke test over hours. |

---

## 10. Conclusion

Hi-EV is no longer a sketch. The daemon runs, the voice/HUD face works, the desktop presence entry point launches daemon + hotkey + tray + voice, and the first tools answer real questions from real memory. The system is also now extensible: new tools, skills, voice backends, and eval cases can be added without editing core code.

But the system is still *reactive* and *manual* in key ways. The path to the vision runs through making EV **continuously aware** (file-system/webhook ingestion), **natively present** (Tauri wrapper, global wake word, desktop capture), **measurable at the skill level**, and **observable** (cost/latency/audit tracing) — in that order.

The good news: every one of those capabilities can be built incrementally on the existing scaffold. The bad news: there is no shortcut. The approved launch plan focuses the next milestone on making EV a **polished, installable Windows app** that watches the filesystem, works by voice end-to-end, measures skill quality, and pauses autonomy safely. Cloud ingress, observability, and advanced OS presence are deferred to v1.1.
