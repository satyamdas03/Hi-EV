# Hi-EV — Honest State Assessment and Roadmap to the Full Vision

> **Date:** 2026-09-17
> **Commit:** `ac630a3`
> **Tests:** 89 passed, 1 skipped
> **Status:** Web/Voice/HUD MVP complete; full operating-system vision still in early innings.

---

## 1. Executive summary

Hi-EV has gone from a README vision to a working local daemon with a browser-native voice/HUD face. The core is real: FastAPI daemon, SQLAlchemy memory, tiered tool registry, personal-only security boundary, GitHub/notes/Gmail/Calendar ingestion, and a React/Three.js frontend that can hear you and answer via WebSocket.

That is a genuine milestone. But against the full vision — *ambient executive layer that wakes up before you do, knows every project and commitment, and acts autonomously within safe tiers* — we are still at roughly **Phase 2.5 of 5+**.

This document is an honest inventory of what works, what is half-built, what is missing, and the shortest credible path from here to the vision.

---

## 2. What is real today

### 2.1 Backend daemon
| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI daemon (`python -m evd`) | ✅ Working | Runs on `127.0.0.1:7345`, health endpoint, CORS for `localhost:5173`. |
| Async SQLAlchemy + SQLite/Postgres | ✅ Working | SQLite fallback works; Postgres target configured. Tests use SQLite. |
| Schema migrations (Alembic) | ✅ Working | Base migration covers projects, ingest, deadlines, people, obligations, events, decisions. |
| Lifespan + alert loop | ✅ Partial | Background loop scans deadlines and prints to stdout, but does **not** push to WebSocket yet. |
| Settings / `.env` | ✅ Working | Pydantic settings, env-file driven, personal-only flag enforced. |

### 2.2 Memory / structured facts
| Component | Status | Notes |
|-----------|--------|-------|
| `Project`, `Ingest`, `Deadline`, `Person`, `Obligation`, `Decision`, `Event` models | ✅ Real | Upsert helpers exist, idempotency by `(source, source_id)`. |
| `MemoryStore` CRUD | ✅ Real | Covers ingestion, deadlines, people, obligations, decisions, events. |
| Vector / semantic document memory | ❌ Missing | No pgvector embeddings, no chunked documents, no hybrid search. |
| Episodic log queryability | ⚠️ Partial | `Event` table exists, but no `ev why` retrieval tool or reasoning over history. |
| Cross-project synthesis | ⚠️ Partial | `brief` aggregates; true synthesis across people/obligations/decisions is hand-rolled, not systematic. |

### 2.3 Ingestion
| Source | Status | Notes |
|--------|--------|-------|
| GitHub personal repos | ✅ Working | Commits, issues, PRs fetched, blocklist enforced. |
| Notes vault (markdown) | ✅ Working | File watcher not implemented — manual ingestion only. |
| Gmail | ✅ Working | Read-only, extracts people, sensitive privacy level. |
| Google Calendar | ✅ Working | Extracts events, deadlines, people, obligations. |
| Web research | ✅ Working | DuckDuckGo + LLM synthesis with citations, Redis cache optional. |
| Active window / laptop context | ❌ Missing | No working-set detection. |
| RSS / changelogs / Telegram | ❌ Missing | Not implemented. |
| Webhook ingress | ❌ Missing | No cloud relay, no GitHub webhooks. |
| Idempotency | ✅ Real | Content-hash + `(source, source_id)` upserts. |

### 2.4 Tools / action layer
| Tool | Tier | Status |
|------|------|--------|
| `status` | T0 | ✅ Works via CLI, REST, WebSocket. |
| `brief` | T0 | ✅ Works. |
| `research` | T0 | ✅ Works, cached. |
| `deadline_watcher` / `alerts` | T0 | ✅ Works; alert loop prints only. |
| `people` | T0 | ✅ Lists. |
| `obligations` | T0 | ✅ Lists. |
| `prep` / `calendar_prep` | T0 | ✅ Works, prep packet from calendar + context. |
| `draft_commit` | T1 | ✅ Works. |
| `draft_pr` | T1 | ✅ Works. |
| `draft_reply` | T1 | ✅ Works. |
| `work_on` (spawn Claude Code) | T1 | ⚠️ Spawns process but pipes context into stdin; Claude Code may not consume it cleanly. |
| `send_email`, `push_branch`, `merge_pr` | T2/T3 | ❌ Not implemented. |
| `remember` explicit capture | T1 | ❌ No CLI command or tool yet. |
| `kill-switch` | T3 guard | ❌ Not implemented. |
| Tier enforcement in WebSocket | ⚠️ | ChatSession refuses T2/T3, but confirmation flow for T2 is not wired end-to-end. |

### 2.5 LLM / reasoning
| Capability | Status | Notes |
|------------|--------|-------|
| Provider-agnostic client (NVIDIA/OpenAI/Anthropic) | ✅ Working | OpenAI-compatible completions. |
| Intent classification | ✅ Working | JSON-only prompt, routes to tools. |
| Chat / direct answer fallback | ✅ Working | General conversation via LLM. |
| Streaming responses | ❌ Missing | Complete response returned in one delta. |
| Deliberate reasoning router | ❌ Missing | No fast/agent/deliberate tiering. |
| Eval harness / golden questions | ❌ Missing | No systematic accuracy measurement. |
| Prompt injection guard | ⚠️ Partial | Content wrapped in tools; no separate guard model. |

### 2.6 Voice / HUD frontend
| Component | Status | Notes |
|-----------|--------|-------|
| Vite + React + TypeScript scaffold | ✅ Working | Builds cleanly. |
| Three.js reactor scene | ✅ Working | Core + particles, shader ring. |
| HUD components | ✅ Working | Boot, Ignition, Hud, Diagnostics, Suggestions. |
| WebSocket bridge | ✅ Working | Auto-reconnect, delta/done/error events. |
| Browser SpeechRecognition STT | ✅ Working | Push-to-talk via Space. |
| Browser speechSynthesis TTS | ✅ Working | Sentence queue, barge-in. |
| Local wake word | ❌ Missing | Push-to-talk only. |
| Local STT (Whisper) | ❌ Missing | Browser API only. |
| Local TTS (Piper/Kokoro) | ❌ Missing | Browser API only. |
| Persistent chat history | ❌ Missing | Per-session only. |
| Proactive server→client alerts | ❌ Missing | Alert loop exists but does not push. |
| HTML blades / model-authored panels | ❌ Missing | Text responses only. |
| System tray / desktop widget | ❌ Missing | Web-only. |

### 2.7 Security / safety
| Component | Status | Notes |
|-----------|--------|-------|
| `personal_only` guard | ✅ Working | Asserted on ingestion sources. |
| Work blocklist (handles + domains) | ✅ Working | Hardcoded to `financialsimplicity`. |
| Privacy levels (`public/personal/sensitive/forbidden`) | ⚠️ Partial | Field exists, but no `forbidden` rejection pipeline or audit event. |
| Tiered tool enforcement | ⚠️ Partial | Tiers declared; T2/T3 confirmation flows incomplete. |
| Kill switch | ❌ Missing | Not implemented. |
| Audit log queryable | ⚠️ Partial | Events logged; no `ev audit` command. |
| Secrets in OS keyring | ❌ Missing | In `.env` only. |
| mTLS to cloud relay | ❌ N/A | No relay yet. |

---

## 3. Maturity against the 10 superpowers

| # | Superpower | Maturity | Honest verdict |
|---|------------|----------|----------------|
| 1 | Ambient awareness | 3/10 | Ingests sources when asked, but no continuous watcher, no ranking, no working-set model. |
| 2 | Voice-first command | 5/10 | Browser voice loop works end-to-end, but push-to-talk and cloud STT/TTS limit the "ambient" feel. |
| 3 | Project memory | 5/10 | Projects, deadlines, people, obligations exist; status answers are real. No vector memory, no deep dossier. |
| 4 | Autonomous execution | 3/10 | T1 drafting + Claude Code spawn work, but no scheduler, no eval harness, no safe T2 confirmation flow. |
| 5 | Cross-project synthesis | 2/10 | `brief` aggregates; true synthesis across commitments/people is not systematic. |
| 6 | Proactive alerts | 2/10 | Deadline watcher runs, but alerts only print to stdout. No push to HUD/phone. |
| 7 | Conversation continuity | 2/10 | WebSocket session has rolling history, but no persistent thread memory or preference learning. |
| 8 | Tool-authoring loop | 0/10 | Not started. |
| 9 | Holographic HUD | 3/10 | Visual shell exists, but it displays text only. No floating blades, no gaze/click-driven UI. |
| 10 | Local, private, inspectable | 5/10 | Runs local, memory local, provenance attached to ingest. But no `ev why`, no kill switch, no audit query UI. |

**Average maturity: ~3.0/10.**

The MVP proved the architecture. The operating-system layer is still ahead.

---

## 4. The hard gaps (what separates MVP from vision)

### Gap 1: Continuous ingestion, not on-demand
Today you must run ingestion manually or via one-off scripts. The vision requires EV to *watch* sources continuously: GitHub webhooks, file-system watcher on notes, Gmail/Calendar poll loops, RSS feeds. Without this, EV cannot be "ambient."

### Gap 2: No document / semantic memory
All memory is structured rows or raw `Ingest.content` strings. There is no chunked, embedded, reranked document store. So EV cannot answer "what did the README say about actuator sizing?" or "summarize the last three design docs."

### Gap 3: No reasoning router
Every request goes through the same simple intent classifier → single tool path. The vision needs a router that picks between fast retrieval, agent loop, or deliberate planning, with cost/latency budgets.

### Gap 4: No eval harness
We cannot measure whether a prompt change made EV better or worse. There are no golden questions, no hallucination rate tracking, no A/B comparison.

### Gap 5: Proactive loop is one-way to stdout
The alert loop computes urgent deadlines but does not push them to the WebSocket, Telegram, tray, or email. Proactive EV does not exist yet.

### Gap 6: T2/T3 confirmation is not trustworthy
T2 actions are supposed to require explicit confirmation, but the confirmation flow is not implemented end-to-end. T3 actions should be hard-blocked; today they are simply not implemented.

### Gap 7: No persistent conversation or preference memory
Each browser tab starts fresh. EV does not remember that you prefer short answers, or that you ignored a deadline reminder twice.

### Gap 8: No system tray / desktop presence
EV is a browser tab. The vision needs a daemon that is present without a browser: hotkey, tray widget, wake word.

---

## 5. Roadmap from today to the vision

We propose **five phases**, each with a clear deliverable and acceptance criteria. The phases are ordered by dependency and user-facing impact.

### Phase A — Ambient Ingestion + Semantic Memory (4–6 weeks)
**Goal:** EV keeps itself up to date and can answer questions over documents, not just structured rows.

**Deliverables:**
1. Continuous ingestion scheduler (`ev.daemon.scheduler`):
   - GitHub webhook endpoint + periodic poll.
   - File-system watcher on notes vault.
   - Gmail/Calendar poll loops (15 min / 1 hour).
   - RSS/changelog feed watcher.
2. Document memory pipeline:
   - Chunk markdown, PDFs, emails, web pages.
   - Local embeddings via Ollama / sentence-transformers.
   - pgvector vector store + BM25 keyword fallback.
   - Hybrid retrieval with rerank.
3. Memory query tool:
   - `memory_search(query, project?)` → ranked chunks with provenance.
   - Update `status` / `prep` / `research` to retrieve from document memory.
4. `ev remember "..."` command → stores explicit facts as `Decision`/`Event`/`Obligation`.

**Acceptance criteria:**
- Running `ev ingest` or waiting 15 minutes updates memory without manual intervention.
- `ev research "what does my notes vault say about X?"` returns cited chunks.
- `ev status RoboCAD` includes relevant recent notes and docs, not just counts.

### Phase B — Reasoning Router + Eval Harness (3–4 weeks)
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
- `pytest tests/eval/` runs in CI and produces a score report.
- A prompt change that lowers eval score is caught before merge.
- WebSocket responses stream word-by-word.

### Phase C — Proactive Alerts + Persistent Context (3–4 weeks)
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
- With browser open, an urgent deadline produces a visible HUD alert within one alert interval.
- Closing and reopening the browser resumes the last conversation.
- `ev brief` can be scheduled and delivered automatically.

### Phase D — Safe Autonomy + Desktop Presence (4–5 weeks)
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
- A simulated "send email" request stops at confirmation and shows exact payload.
- Push to `main` is refused regardless of prompt or voice command.
- Hotkey activates EV from any app.

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

1. **Migration base revision drift.** We edited the base migration to fix missing columns, which is fine for a pre-production repo but must stop once production data exists. Introduce strict migration discipline after Phase A.
2. **Work blocklist is hardcoded.** `financialsimplicity` is burned into `GitHubIngestion` and `NotesIngestion`. Move to config.
3. **Claude Code spawn is fragile.** `work_on` pipes context into stdin of `claude code`; the CLI likely ignores it. Move to a context file or dedicated launch protocol.
4. **Redis assumed but optional.** Research tool degrades gracefully, but other features may assume Redis. Make Redis optional everywhere or document it as required.
5. **Secrets in `.env`.** Move to OS keyring or encrypted store before Phase D.
6. **No structured logging / observability.** Add OpenTelemetry or structured logs for cost/latency/audit tracing.

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

If the next sprint is 1–2 weeks, focus on the highest-leverage gap: **ambient ingestion + semantic memory**. This unlocks everything else.

**Sprint goal:** EV keeps memory fresh without manual commands, and can answer questions over notes/docs with citations.

**Tasks:**
1. Add `scripts/ingest_all.py` that runs GitHub + notes + Gmail + Calendar ingestion in one pass.
2. Add a scheduler loop in the daemon that runs ingestion every 15–60 minutes.
3. Add document chunking + local embeddings (`sentence-transformers` or Ollama `nomic-embed-text`).
4. Add `MemoryStore.search_documents(query, project?)` using keyword + vector hybrid.
5. Update `StatusTool` to include top document chunks in its context prompt.
6. Add `ev remember <fact>` CLI command and WebSocket intent.
7. Add eval questions for status/research accuracy.

**Acceptance criteria:**
- `python scripts/ingest_all.py` updates all sources in <60 seconds.
- After ingestion, `ev status RoboCAD` references actual recent note content.
- `ev research "from my notes: what did I decide about X?"` returns cited chunks.
- New eval harness runs with ≥70% pass rate on golden questions.

---

## 9. Metrics to track

| Metric | Target by end of Phase A | How to measure |
|--------|--------------------------|----------------|
| Ingestion freshness | <15 minutes for notes, <1 hour for GitHub | Scheduler intervals + last ingest timestamp. |
| Status answer accuracy | ≥80% on golden status questions | Eval harness. |
| Research citation correctness | ≥85% citations point to real source | Manual spot-check + eval. |
| Intent classification accuracy | ≥90% | Labeled transcript test set. |
| End-to-end voice latency | <5s from speech stop to first delta | Smoke test timing. |
| WebSocket uptime | 99.9% local | Smoke test over hours. |

---

## 10. Conclusion

Hi-EV is no longer a sketch. The daemon runs, the voice/HUD face works, and the first tools answer real questions from real memory. But the system is still *reactive* and *manual*. The path to the vision runs through making EV **continuously aware**, **semantically literate**, **measurable**, **proactive**, and **safely autonomous** — in that order.

The good news: every one of those capabilities can be built incrementally on the existing scaffold. The bad news: there is no shortcut. The next milestone is not another UI polish; it is making EV actually know what changed while you were away.
