# Hi-EV — End-to-End Launch Roadmap

> **Date:** 2026-10-04
> **Goal:** Get Hi-EV from its current state to a polished, testable, launch-ready Windows product.
> **Voice strategy:** Local-first (`faster-whisper` + Kokoro/pyttsx3) with browser fallback; LiveKit optional post-launch.
> **Launch scope:** Polished local Windows app + file-system watcher + full test coverage. Cloud relay, observability, macOS/Linux, and tool self-authoring move to v1.1 / Phase H.
> **Status:** G1 complete, G2 complete, G3 next.

---

## 1. Current state at the start of this plan

- Phases A–F are complete and pushed to `origin/main`.
- Phase G Tauri desktop wrapper skeleton is built:
  - Native window, system tray, global shortcut, daemon manager.
  - Windows MSI installer produced.
  - Security hardened: shell permissions removed, CSP added, devUrl pinned to 127.0.0.1.
- Local voice pipeline exists (`ev.voice`) but is **opt-in and not exercised by default**.
- File-system watcher is **not implemented**; ingestion is scheduler-driven.
- Skill eval golden datasets are **not implemented**.
- Cloud relay / webhook ingress is **not implemented**.
- Observability / cost tracing / `ev why` is **not implemented**.
- OpenJarvis pattern is adopted; direct OpenJarvis code/skill integration is **not implemented**.

**Verification baseline:**
- `python -m pytest` → 260 passed, 1 skipped
- `ruff check .` → clean
- `cd web && npm run build` → clean
- `cd desktop/src-tauri && cargo check && cargo clippy -- -D warnings` → clean
- `cd desktop && npm run tauri:build` → Windows MSI produced

---

## 2. Definition of launch-ready

A non-technical user on Windows can:

1. Download `Hi-EV_0.x.x_x64_en-US.msi`.
2. Install it.
3. Open the app.
4. See the setup wizard if Python or an LLM key is missing.
5. Complete setup.
6. Land in the HUD and talk/type to EV.
7. Press `Ctrl+Alt+E` (or click a mic button) and speak a command.
8. See EV respond by voice and text.
9. Add a file to their notes vault and see it reflected in memory within minutes.
10. Trust that T2 actions pause for confirmation and T3 actions are blocked.

And the full test suite passes with no new skips or warnings.

---

## 3. Phases to launch

### ✅ Phase G1 — Tauri Launch Polish (complete)

**Goal:** Turn the Tauri skeleton into a reliable, first-run-friendly Windows installer.

**Deliverables:**
1. ✅ Replaced placeholder icons with a generated Hi-EV logo set (`scripts/generate_icons.py`).
2. ✅ Extended setup wizard (`SetupWizard.tsx` + backend `/setup`) to:
   - Detect Python ≥3.12 on the system.
   - Show a download link and block first-run completion if Python is missing.
   - Validate that at least one LLM key is present.
3. ✅ Made global shortcut configurable via `.env` (`EV_GLOBAL_HOTKEY`).
4. ✅ Added daemon crash recovery: if `python -m evd` exits unexpectedly, a native notification is shown.
5. ✅ Native notification when daemon becomes healthy and the HUD is ready.
6. ✅ Added "Check for updates" to tray menu wired to `/update/check`.
7. ✅ Ensured quitting Tauri reliably terminates the daemon child process.
8. ✅ Tauri artifact smoke test script `scripts/smoke_tauri.py` (clean-VM MSI install still manual).

**Acceptance criteria:**
- ✅ `npm run tauri:build` produces an MSI.
- ✅ Without Python, the setup wizard refuses to proceed and links to python.org.
- ✅ With Python, the app starts the daemon and shows the HUD.
- ✅ Tray hide/show, update check, and quit work.
- ✅ Global shortcut can be changed via `.env`.

**Verification:** 255 passed, 1 skipped; ruff clean; frontend build clean; Tauri `cargo clippy` clean; MSI produced; `scripts/smoke_tauri.py` passed.

---

### ✅ Phase G2 — File-System Watcher (complete)

**Goal:** Make EV event-driven for local notes and project files instead of polling every 5 minutes.

**Deliverables:**
1. ✅ New `ev.ingestion.watcher` package using `watchdog`:
   - Watch `settings.notes_path` recursively.
   - Watch configured project paths (`robocad_path`, `learningrobotics_path`, `hiev_path`) recursively.
2. ✅ Debounce and coalesce file-change events with a 2-second quiet period.
3. ✅ Incremental ingestion:
   - Detect changed/deleted `.md` files.
   - Upsert `Ingest` rows and re-chunk/update `DocumentChunk` + vector entries.
   - Delete removed notes from both chunks and `Ingest` rows.
4. ✅ Hook watcher into FastAPI lifespan (start on daemon launch, stop on shutdown).

**Acceptance criteria:**
- ✅ Adding a `.md` file to the notes vault is queryable via memory search within seconds.
- ✅ Deleting a note removes its chunks from the vector store.
- ✅ Full test suite still passes.
- ✅ Watcher tests cover create, modify, delete, and non-`.md` events.

**Verification:** 260 passed, 1 skipped; ruff clean.

**Dependencies:** Phase G1 complete (daemon lifecycle stable).

---

### 🚧 Phase G3 — Voice End-to-End (next)

**Goal:** Voice works out of the box in the Tauri app and browser HUD.

**Deliverables:**
1. Audit and fix any voice backend edge cases:
   - `faster-whisper` model download/cache path under `%LOCALAPPDATA%\Hi-EV\models`.
   - Kokoro voice model download/cache.
   - pyttsx3 fallback when heavier models are missing.
2. Add voice settings to setup wizard:
   - Enable/disable voice.
   - Choose STT backend (`faster_whisper` / `mock`).
   - Choose TTS backend (`kokoro` / `pyttsx3` / `mock`).
3. Ensure Tauri global shortcut triggers a full voice turn:
   - Record → transcribe → `POST /voice/chat` → synthesize → play.
4. Add a visible mic button in HUD that uses browser SpeechRecognition when local voice is disabled or unavailable.
5. Add `scripts/smoke_voice.py` that runs a headless voice turn with the mock backend end-to-end.
6. Document voice setup in `README.md`.

**Acceptance criteria:**
- With voice enabled and mock backend, pressing `Ctrl+Alt+E` produces a spoken response.
- With `faster-whisper` + `pyttsx3` installed, the same flow works offline.
- Browser HUD mic button works as fallback.
- `python scripts/smoke_voice.py` passes.

**Dependencies:** Phase G1.

---

### Phase G4 — Skill Eval Golden Datasets

**Goal:** Prove that built-in skills work and catch regressions.

**Deliverables:**
1. Create `tests/eval/skills/` golden datasets:
   - `hello_ev` — greeting and name recall.
   - `summarize_notes` — summarize a seeded note file.
2. Add skill eval runner that:
   - Loads a skill.
   - Runs it through the tool registry with seeded context.
   - Checks output with `contains` / `exact` / `regex`.
   - Reports per-skill pass rate and latency.
3. Add `ev eval run --skills` CLI flag or `ev eval skills` command.
4. Fix any skill that fails golden checks.

**Acceptance criteria:**
- `ev eval skills` produces a JSON/HTML report.
- All built-in skills pass.
- Eval runs in CI without external API keys (mock LLM or seeded fixtures).

**Dependencies:** Phase F eval runner already exists.

---

### Phase G5 — Security, Safety & Kill Switch

**Goal:** Close the remaining safety gaps before users trust EV with real data.

**Deliverables:**
1. Implement kill switch:
   - New `EV_KILL_SWITCH=true` setting.
   - When enabled, all ingestion loops, alert loops, and T1/T2 actions pause.
   - HUD shows a prominent "read-only / kill switch active" banner.
   - CLI command: `ev kill` toggles it and writes to `.env`.
2. Audit log:
   - Ensure every tool call is logged with timestamp, tier, source, params hash, outcome.
   - Add `POST /audit` query endpoint or CLI `ev audit recent` (lightweight v1.0 version of `ev why`).
3. Review personal-only boundary enforcement end-to-end.
4. Add a clear setup step for blocked handles/domains.
5. Ensure secrets vault is initialized on first run if master password is set.

**Acceptance criteria:**
- `EV_KILL_SWITCH=true` stops proactive loops and blocks T1/T2 actions in web/voice/CLI.
- T3 actions remain hard-blocked regardless of kill switch.
- Audit endpoint returns recent tool calls.

**Dependencies:** Phase G1.

---

### Phase G6 — Final Integration, Packaging & Test Sweep

**Goal:** Verify the complete product end-to-end and ship.

**Deliverables:**
1. End-to-end smoke test suite:
   - Install MSI → launch → setup wizard → HUD loads → send text message → get response.
   - Global shortcut → voice turn with mock backend → spoken response.
   - Add note → file watcher ingests → query memory → answer references new note.
   - T2 action (e.g., sandbox tool) pauses for confirmation; deny cancels.
   - T3 action (push to main) is refused.
2. Performance benchmark:
   - First response time, voice turn latency, memory query latency.
3. Clean uninstall verification (no leftover daemons, no orphaned `%LOCALAPPDATA%\Hi-EV` files we did not create).
4. Final documentation pass:
   - README install instructions.
   - `.env.example` updated for launch.
   - Troubleshooting guide.
5. Version bump and changelog.

**Acceptance criteria:**
- `python -m pytest` → all passing, 0 new skips.
- `ruff check .` clean.
- `cd web && npm run build` clean.
- `cd desktop/src-tauri && cargo check && cargo clippy -- -D warnings` clean.
- `cd desktop && npm run tauri:build` produces MSI.
- Smoke test script passes on a clean Windows environment.

**Dependencies:** Phases G1–G5 complete.

---

## 4. Post-launch roadmap (Phase H)

After the Windows local launch:

1. **Cloud relay / webhook ingress** — durable mailbox for GitHub/Telegram while laptop sleeps.
2. **macOS + Linux installers** — CI builds and code-signing/notarization.
3. **Observability / cost tracing / `ev why`** — OpenTelemetry or structured JSON logs.
4. **Optional LiveKit cloud voice** — high-quality turn-taking for users who opt in; local voice remains default.
5. **Tool self-authoring loop** — EV proposes and grows Python tools via sandboxed iterations.
6. **Real OpenJarvis code/skill integration** — if community skill compatibility becomes a requirement.

---

## 5. OpenJarvis clarification

**Decision for launch:** We will not pursue direct OpenJarvis codebase integration for v1.0.

- Phase F already delivered an OpenJarvis-*style* plugin architecture (`ev.core.registry`, `@register`, `SKILL.md` skills).
- That architecture is real, tested, and extensible.
- Direct import of OpenJarvis plugins/skills would require aligning APIs, dependency versions, and security models — a multi-day integration that is not a launch blocker.
- If community skill reuse becomes critical after launch, it becomes a Phase H workstream.

---

## 6. Recommended execution order and rough timeline

Assuming focused daily sessions:

| Phase | Duration | Owner | Can parallelize? |
|-------|----------|-------|------------------|
| G1 Tauri polish | 1 session | Claude + you review icons | No |
| G2 File-system watcher | 1–2 sessions | Claude | No (depends on G1) |
| G3 Voice end-to-end | 1–2 sessions | Claude | No (depends on G1) |
| G4 Skill eval golden datasets | 1 session | Claude | Parallel with G3 if needed |
| G5 Security / kill switch / audit | 1 session | Claude | No |
| G6 Final integration & test sweep | 1–2 sessions | Claude + you run smoke tests | No |

**Estimated total:** 6–10 focused sessions to reach launch-ready.

---

## 7. Immediate next step

Approve this plan, then start **Phase G1 — Tauri Launch Polish**:

1. Get or create a real Hi-EV logo/icon set.
2. Extend the setup wizard with Python detection.
3. Make the global shortcut configurable.
4. Add daemon crash recovery.

This is the highest-leverage first move because it turns the existing skeleton into a reliable installer — the front door of the product.

---

## 8. Approval checklist

- [ ] Voice: local-first default, LiveKit post-launch — approved.
- [ ] Launch scope: polished Windows local app + watcher + tests; cloud/observability v1.1 — approved.
- [ ] OpenJarvis: pattern adopted, direct integration deferred — approved.
- [ ] Phase order G1 → G2 → G3 → G4 → G5 → G6 — approved.
- [ ] Ready to begin Phase G1 — approved.
