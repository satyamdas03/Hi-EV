# Hi-EV — Honest State Assessment and Roadmap to the Full Vision

> **Date:** 2026-09-22 (updated)
> **Commit:** `92ff90d`
> **Tests:** 197 passed, 1 skipped
> **Ruff:** clean
> **Frontend build:** clean
> **Status:** Web/Voice/HUD MVP complete. Phases A–D complete and pushed to `origin/main`. Phase E — Local Voice + Advanced HUD + Self-Expansion is next.

---

## 1. Executive summary

Hi-EV has gone from a README vision to a working local daemon with a browser-native voice/HUD face. The core is real: FastAPI daemon, SQLAlchemy memory, tiered tool registry, personal-only security boundary, GitHub/notes/Gmail/Calendar ingestion, and a React/Three.js frontend that can hear you and answer via WebSocket.

That is a genuine milestone. But against the full vision — *ambient executive layer that wakes up before you do, knows every project and commitment, and acts autonomously within safe tiers* — we are now at roughly **Phase 4 of 5+**.

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
| Settings / `.env` | ✅ Working | Pydantic settings, env-file driven, personal-only flag enforced, Phase D desktop flags added. |

### 2.2 Memory / structured facts
| Component | Status | Notes |
|-----------|--------|-------|
| `Project`, `Ingest`, `Deadline`, `Person`, `Obligation`, `Decision`, `Event` models | ✅ Real | Upsert helpers exist, idempotency by `(source, source_id)`. |
| `MemoryStore` CRUD | ✅ Real | Covers ingestion, deadlines, people, obligations, decisions, events. |
| Vector / semantic document memory | ✅ Working | `DocumentChunk` model, sqlite-vec vector table, local embeddings, chunking pipeline, hybrid search, `memory_search` tool, and `ev remember` command are implemented. |
| Episodic log queryability | ⚠️ Partial | `Event` table exists; chat turns are persisted, but no `ev why` retrieval tool or reasoning over history. |
| Cross-project synthesis | ⚠️ Partial | `brief` aggregates; true synthesis across people/obligations/decisions is hand-rolled, not systematic. |
| Preference memory | ❌ Missing | No tracking of ignored reminders, preferred answer length, or voice speed.

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

### 2.5 LLM / reasoning
| Capability | Status | Notes |
|------------|--------|-------|
| Provider-agnostic client (NVIDIA/OpenAI/Anthropic) | ✅ Working | OpenAI-compatible completions + streaming SSE. |
| Intent classification | ✅ Working | JSON-only prompt, routes to tools. |
| Chat / direct answer fallback | ✅ Working | General conversation via LLM; fast path streams. |
| Streaming responses | ✅ Working | `LLMClient.complete_stream()` yields deltas; WebSocket fast-chat path streams word-by-word with stop control. |
| Reasoning router | ✅ Working | Heuristic fast/agent/deliberate classifier with optional LLM fallback; emits `phase: route:<path>`. |
| Eval harness / golden questions | ✅ Working | `tests/eval/` with seeded fixtures, judge, per-category evals, `scripts/run_eval.py` report. |
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
| Local wake word | ⚠️ Browser | Browser Web Speech API continuous recognition for "hey ev"; local Porcupine/openWakeWord moved to Phase E. |
| Local STT (Whisper) | ❌ Missing | Browser API only. |
| Local TTS (Piper/Kokoro) | ❌ Missing | Browser API only. |
| Persistent chat history | ✅ Working | Chat threads persist across reconnects; thread CRUD in UI. |
| Proactive server→client alerts | ✅ Working | `_alert_loop` pushes `type: alert` to all WebSockets. |
| HTML blades / model-authored panels | ❌ Missing | Text responses only. |
| System tray / desktop widget | ⚠️ Skeleton | `scripts/global_hotkey.py` (Ctrl+Alt+E) + `scripts/tray_widget.py` (pystray); not yet packaged as single entry point. |

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
| Secrets in OS keyring | ❌ Missing | In `.env` only. |
| mTLS to cloud relay | ❌ N/A | No relay yet. |

---

## 3. Maturity against the 10 superpowers

| # | Superpower | Maturity | Honest verdict |
|---|------------|----------|----------------|
| 1 | Ambient awareness | 7/10 | Background ingestion scheduler polls notes, GitHub, Gmail, Calendar; long-form content is chunked, embedded, and indexed. File-system watcher and webhook ingress remain future work. |
| 2 | Voice-first command | 6/10 | Browser voice loop works end-to-end; wake word "hey ev" works in browser. Local STT/TTS still pending. |
| 3 | Project memory | 8/10 | Structured facts + document chunks + hybrid search; router/eval measure retrieval quality. No deep dossier reasoning yet. |
| 4 | Autonomous execution | 7/10 | Tiered enforcement works: T0/T1 auto-run, T2 confirms in web/voice/CLI, T3 hard-blocked. Tool-authoring loop not started. |
| 5 | Cross-project synthesis | 6/10 | Memory snippets surface across tools; brief aggregates. True synthesis across commitments/people is still hand-rolled. |
| 6 | Proactive alerts | 7/10 | WebSocket push alerts, morning brief scheduler, Telegram skeleton; no phone/email fallback yet. |
| 7 | Conversation continuity | 8/10 | Persistent chat threads across reconnects and reloads; no preference learning yet. |
| 8 | Tool-authoring loop | 0/10 | Not started. |
| 9 | Holographic HUD | 4/10 | Visual shell + chat/alerts/thread panels; still text-only, no model-authored blades or gaze/click UI. |
| 10 | Local, private, inspectable | 6/10 | Runs local, memory local, provenance attached to ingest, guard + tier enforcement. No `ev why`, no kill switch, no audit query UI, secrets still in `.env`. |

**Average maturity: ~5.9/10.**

Phases A–D closed the core operating-system layer. EV is now ambient, measurable, proactive, persistent, and safely autonomous. Phase E will make it fully local-voice and self-expanding.

---

## 4. The hard gaps (what separates MVP from vision)

### Gap 1: File-system watcher and webhook ingress
Ingestion is still primarily scheduler-driven. The vision requires EV to *watch* sources continuously: GitHub webhooks, file-system watcher on notes, RSS feeds. Without this, EV is ambient-but-polling rather than truly event-driven.

### Gap 2: Document / semantic memory — LARGELY CLOSED
`DocumentChunk` + sqlite-vec + hybrid search + grounded tools now answer "what did the README say about actuator sizing?" from indexed documents. What remains is deeper reasoning over documents (summaries, compare/contrast, trend detection), a true reranker, and cross-document synthesis.

### Gap 3: Reasoning router — CLOSED
`ev.reasoning.router` now classifies requests into fast/agent/deliberate paths and is integrated into the WebSocket chat path. Cost/latency budgets and deeper deliberation loops remain future polish.

### Gap 4: Eval harness — CLOSED
`tests/eval/` and `scripts/run_eval.py` provide golden-question evals for status, memory, research, prep, and guard refusal with correctness, latency, and cost metrics.

### Gap 5: Proactive loop — CLOSED
The alert loop now pushes `type: alert` events to all active WebSockets. A morning brief scheduler fires at the configured time. Telegram relay skeleton is wired but disabled by default; phone/email fallback remains future work.

### Gap 6: T2/T3 confirmation — CLOSED
T2 actions pause for a `type: confirm` message and wait for `confirm_response` in WebSocket, voice, and CLI. T3 actions are hard-blocked in web/voice. The guard downgrades tier for untrusted sources.

### Gap 7: Persistent conversation — CLOSED; preference memory remains
Chat threads persist across reconnects and page reloads. EV does not yet learn from ignored reminders or preferred answer length/voice speed.

### Gap 8: Desktop presence — SKELETON COMPLETE
Global hotkey (`Ctrl+Alt+E`), system-tray widget skeleton (`pystray`), and browser wake word ("hey ev") are implemented. They are not yet packaged as a single installable desktop entry point.

### Gap 9: No local STT/TTS
Voice still depends on browser SpeechRecognition and speechSynthesis. A true ambient assistant needs local faster-whisper + Piper/Kokoro so it works offline and with lower latency.

### Gap 10: No tool-authoring loop, structured observability, or encrypted secrets
EV cannot yet propose and grow its own tools, trace cost/latency/audit in one place, or store tokens outside `.env`.

---

## 5. Roadmap from today to the vision

We propose **five phases**, each with a clear deliverable and acceptance criteria. The phases are ordered by dependency and user-facing impact.

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

### Phase E — Local Voice + Advanced HUD + Self-Expansion (6+ weeks)
**Goal:** Full local-first voice, holographic information space, and the ability to grow its own tools.

**Deliverables:**
1. Local STT/TTS:
   - faster-whisper for transcription.
   - Piper or Kokoro for TTS.
2. Model-authored HTML blades:
   - Sanitized, schema-constrained panels for status, deadlines, prep.
   - Python sanitizer; no arbitrary JS.
3. Hand tracking / gaze-driven UI (optional).
4. Tool-authoring loop:
   - EV proposes a new tool from description.
   - Generates Python + test + registers it.
   - Human approval before activation.
5. Self-tuning:
   - Tracks which summaries were ignored vs acted on.
   - Tunes retrieval thresholds and alert frequency.

**Acceptance criteria:**
- Voice works with no cloud dependency for common queries.
- EV can display a deadline as a clickable blade with source links.
- A new tool can be added from a one-paragraph description in under 10 minutes.

---

## 6. Technical debt to pay down soon

1. **Migration base revision drift — RESOLVED.** Migration discipline is now documented in `docs/development/migrations.md`; base revision `aacdc9089a90` is frozen. Chat-thread and trusted-source migrations added.
2. **Work blocklist is hardcoded — RESOLVED.** Blocklist is config-driven via `EV_BLOCKED_HANDLES` / `EV_BLOCKED_DOMAINS`.
3. **Claude Code spawn is fragile.** `work_on` pipes context into stdin of `claude code`; the CLI likely ignores it. Move to a context file or dedicated launch protocol.
4. **Redis assumed but optional.** Research tool degrades gracefully, but other features may assume Redis. Make Redis optional everywhere or document it as required.
5. **Secrets in `.env` — STILL OPEN.** Move to OS keyring or encrypted store in Phase E.
6. **No structured logging / observability — STILL OPEN.** Add OpenTelemetry or structured logs for cost/latency/audit tracing in Phase E.
7. **Desktop presence not packaged.** Hotkey, tray, and wake-word scripts are separate; create a single `scripts/desktop_presence.py` entry point in Phase E.

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

---

## 8. What to build next (recommended immediate sprint)

Phases A–D are complete. The next highest-leverage work is **Phase E — Local Voice + Advanced HUD + Self-Expansion** so EV works offline by voice, displays model-authored information blades, and can grow its own tools.

**Sprint goal:** Local STT/TTS replaces browser Speech APIs, the desktop presence scripts are packaged into one entry point, EV renders its first HTML blade, and a tool-authoring prototype generates a tool + test from a description.

**Tasks:**
1. Local STT/TTS pipeline: faster-whisper + Piper or Kokoro, replacing browser SpeechRecognition/speechSynthesis.
2. Package desktop presence: single `scripts/desktop_presence.py` entry point that launches hotkey listener, tray widget, and optional wake-word detector.
3. HTML blade renderer: sanitized, schema-constrained panels for status, deadlines, prep; Python sanitizer blocks arbitrary JS.
4. Tool-authoring loop prototype: generate Python tool + test from a one-paragraph description; human approval before registration.
5. Move secrets out of `.env` into OS keyring or encrypted store.

**Acceptance criteria:**
- Voice query works with no cloud dependency for common queries.
- `scripts/desktop_presence.py` launches and surfaces tray + hotkey focus.
- EV displays a deadline as a clickable blade with source links.
- A new tool can be added from a one-paragraph description in under 10 minutes.
- Full test suite still passes; ruff clean; frontend build clean.

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

Hi-EV is no longer a sketch. The daemon runs, the voice/HUD face works, and the first tools answer real questions from real memory. But the system is still *reactive* and *manual*. The path to the vision runs through making EV **continuously aware**, **semantically literate**, **measurable**, **proactive**, and **safely autonomous** — in that order.

The good news: every one of those capabilities can be built incrementally on the existing scaffold. The bad news: there is no shortcut. The next milestone is not another UI polish; it is making EV fully local-voice, self-expanding, and present on the desktop without a browser tab.
