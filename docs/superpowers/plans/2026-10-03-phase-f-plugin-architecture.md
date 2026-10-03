# Phase F — Plugin Architecture, Skills, Voice, Sandbox, Eval, Secrets, and Auto-Updater

> **Date:** 2026-10-03
> **Goal:** Turn Hi-EV from a hardcoded tool list into an extensible personal AI OS with an OpenJarvis-style plugin registry, prompt-based skills, a local voice pipeline, safe code execution, a reusable eval runner, encrypted secrets, and a read-only auto-updater.
> **Status:** ✅ COMPLETE and pushed to `origin/main` (`02781e2`).
> **Previous phase:** [Phase E — Launch MVP](2026-10-02-phase-e-launch-mvp.md)

---

## Why this phase

The original tool system was a manually-curated list. That does not scale to a personal AI OS where users, skills, agents, voice backends, and eval cases should be addable without editing core code. Phase F ports and adapts the OpenJarvis-style plugin architecture into Hi-EV, adds the missing local-first voice layer, and ships the surrounding infrastructure (sandbox, eval, secrets, updater) that makes the system safe and maintainable as it grows.

---

## Deliverables

### 1. Core registry + ABCs (`ev.core`)

**Files:**
- `src/ev/core/registry.py`
- `src/ev/core/component.py`
- `src/ev/core/discovery.py`

**What:**
- `RegistryBase[T]` with a global `@register(kind, name)` decorator.
- Registries live in `ev.core.registry.registry` for `tool`, `agent`, `memory`, `engine`, `skill`, `stt`, and `tts`.
- `ev.core.component` defines `BaseTool`, `BaseAgent`, `BaseMemory`, `BaseEngine`, `BaseSkill`, plus `AgentContext`/`AgentResult`.
- `ev.core.discovery.discover_package` / `discover_all` use `pkgutil` to import modules and trigger decorators on startup.
- `ev.tools.registry.ToolRegistry` was preserved as a thin layer over the global registry, so existing callers and tests keep working.

**Acceptance criteria:**
- ✅ Every existing tool registers via the decorator.
- ✅ `ev.server.api` drops manual imports and uses `_tool_registry(store)` with auto-discovery.
- ✅ Existing tests still pass without changes.

### 2. Tool conversion

**What:**
All existing tools now register via the decorator:
`status_tool`, `brief_tool`, `memory_tool`, `remember_tool`, `research_tool`, `work_tool`, `draft_tools`, `calendar_prep_tool`, `alerts_tool`, `deadline_watcher`, `prep_tool`, `obligations_tool`, `people_tool`.

**Acceptance criteria:**
- ✅ `python -m evd` starts and discovers all tools.
- ✅ REST and WebSocket endpoints can call any registered tool.

### 3. Agents and skills (`ev.skills`)

**Files:**
- `src/ev/skills/loader.py`
- `src/ev/skills/manifest.py`
- `src/ev/skills/skill_tool.py`
- `skills/*/SKILL.md`

**What:**
- `ev.agents.simple` and `ev.agents.orchestrator` are `@register("agent", ...)` agents.
- `ev.skills` loads `SKILL.md` files (YAML frontmatter + body prompt template), parses manifests, discovers skills at runtime, and exposes each as a tool through `SkillTool` / `SkillToolAdapter`.
- Built-in skills: `hello_ev` and `summarize_notes` under `skills/`.
- Server startup calls `load_skills_into_registry()` when `enable_skills` is true.
- New REST endpoint `GET /skills` and CLI command `ev skills list`.

**Acceptance criteria:**
- ✅ `GET /skills` returns the discovered skill catalog.
- ✅ `ev skills list` prints skill names and descriptions.
- ✅ A skill can be invoked through the same tool path as Python tools.

### 4. Local voice pipeline (`ev.voice`)

**Files:**
- `src/ev/voice/component.py`
- `src/ev/voice/io.py`
- `src/ev/voice/manager.py`
- `src/ev/voice/backends/*.py`

**What:**
- `ev.voice.component` defines `BaseSTTBackend` and `BaseTTSBackend`.
- Backends are registered via decorators:
  - STT: `faster_whisper`, `mock`
  - TTS: `kokoro`, `pyttsx3`, `mock`
- `ev.voice.io` records/playback; it falls back to stdlib `wave` when `soundfile` is unavailable so tests and degraded installs still work.
- `ev.voice.manager.VoiceManager` selects the best available backend from config (`voice_stt_backend`, `voice_tts_backend`) and provides `listen_and_transcribe()` and `say()`.
- `pyproject.toml` gained `[voice]` extras (`faster-whisper`, `kokoro`, `pyttsx3`, `sounddevice`, `soundfile`) and `greenlet>=3.0.0` in core deps.

**Acceptance criteria:**
- ✅ Voice works with mock backends in CI.
- ✅ With `[voice]` extras installed, faster-whisper STT and Kokoro/pyttsx3 TTS can be selected via env vars.
- ✅ `ev.config` exposes `voice_enabled`, `voice_stt_backend`, `voice_tts_backend`, `voice_model_dir`.

### 5. Desktop presence voice loop

**File:** `scripts/desktop_presence.py`

**What:**
- `scripts/desktop_presence.py` lazily creates a `VoiceManager` when `voice_enabled` is true.
- Pressing the global hotkey (`ctrl+alt+e` by default) still focuses the HUD via `POST /focus`, and now also starts a voice turn in a background thread: record → transcribe → `POST /voice/chat` → synthesize and speak the reply.
- A `_voice_busy` flag prevents overlapping turns.

**Acceptance criteria:**
- ✅ With voice enabled, pressing `Ctrl+Alt+E` records, transcribes, chats, and speaks the reply.
- ✅ Overlapping turns are prevented.
- ✅ Without voice extras, the desktop entry point still launches daemon, hotkey, and tray.

### 6. REST additions

**What:**
- `POST /voice/chat` — synchronous text-in/text-out chat path used by the desktop voice client. It runs the same guard/router/tool path as the WebSocket chat by driving `ChatSession` with a capturing fake WebSocket.
- `GET /skills` — discovered skill catalog.

**Acceptance criteria:**
- ✅ `POST /voice/chat` returns a text response.
- ✅ `GET /skills` returns skill metadata.

### 7. Safe code sandbox (`ev.sandbox`)

**Files:**
- `src/ev/sandbox/policy.py`
- `src/ev/sandbox/runner.py`
- `src/ev/sandbox/isolated.py`
- `src/ev/tools/sandbox_tool.py`

**What:**
- `ev.sandbox` package with `SandboxPolicy`, `CodeRunner`, `isolated` subprocess runner, and `SandboxTool`.
- Static AST checks allow a small whitelist of stdlib imports (`math`, `json`, `datetime`, etc.) and ban dangerous builtins (`open`, `exec`, `eval`, `__import__`, etc.).
- Snippets run in a subprocess with a configurable timeout; `input_data` is provided and the final value of `result` is returned.
- `SandboxTool` is tier 2, so the HUD/voice UI requires user confirmation.
- Wired into `ChatSession` so the orchestrator can dispatch generated helper snippets.
- `SandboxTool` was moved into `ev.tools.sandbox_tool` so the auto-discovering registry finds it.

**Acceptance criteria:**
- ✅ Sandbox blocks dangerous imports and builtins.
- ✅ Allowed stdlib snippets run and return their `result`.
- ✅ `SandboxTool` is tier 2 and pauses for confirmation in web/voice.

### 8. Eval runner abstraction (`ev.eval`)

**Files:**
- `src/ev/eval/case.py`
- `src/ev/eval/suite.py`
- `src/ev/eval/runner.py`
- `src/ev/eval/checks.py`
- `src/ev/eval/loader.py`

**What:**
- `ev.eval` package with `EvalCase`, `EvalSuite`, `EvalResult`, checks (`contains`, `exact`, `regex`, `json_path`), JSON/YAML loader, runner, and reporter.
- `EvalRunner` discovers suite files, executes tool calls through the live `ToolRegistry`, and produces pass/fail reports with per-case latency.
- CLI: `ev eval run [suite_dir]` with `--json` output.

**Acceptance criteria:**
- ✅ `ev eval run tests/eval/suites` (or equivalent) produces a pass/fail report.
- ✅ `--json` output is valid JSON.
- ✅ Checks cover contains, exact, regex, and json_path.

### 9. Encrypted secrets vault (`ev.secrets`)

**Files:**
- `src/ev/secrets/store.py`

**What:**
- `ev.secrets` package with `EncryptedSecretStore` backed by `cryptography.fernet`.
- Vault JSON file stores encrypted key/value pairs. The encryption key is retrieved from the OS credential store via `keyring` when available, otherwise derived from `EV_MASTER_PASSWORD`.
- `get_settings()` loads the vault into `os.environ` before pydantic reads environment variables, so encrypted secrets override `.env` values.
- CLI commands: `ev secrets set/get/list/delete`.
- Added `[secrets]` extras and dev dependencies for `cryptography` and `keyring`; added a `.gitignore` exception for `src/ev/secrets/`.

**Acceptance criteria:**
- ✅ `ev secrets set KEY value` encrypts and stores the value.
- ✅ `ev secrets get KEY` decrypts and returns it.
- ✅ Without keyring, `EV_MASTER_PASSWORD` unlocks the vault.
- ✅ Secrets loaded from the vault override `.env` values.

### 10. Auto-updater and desktop presence rewrite (`ev.updater`)

**Files:**
- `src/ev/updater/checker.py`
- `scripts/desktop_presence.py`
- `tests/test_updater.py`

**What:**
- `src/ev/updater/checker.py` provides `UpdateChecker`, a read-only GitHub releases comparator. It reports whether a newer release exists and prints the installer URL; it never downloads or runs code without user confirmation.
- New CLI command: `ev update [--repo owner/repo] [--json]`.
- `scripts/desktop_presence.py` was repaired: restored `_focus_hiev`, `_run_hotkey`, `_run_tray`, and added `_check_updates(base_url)` so the system-tray "Check for updates" item works.
- `tests/test_updater.py` covers update-available, up-to-date, network-error, and version-normalization paths.
- Stabilized `tests/test_proactive_alerts.py` by cancelling leftover async tasks before teardown, eliminating the SQLite "database is locked" error that appeared in full-suite runs.

**Acceptance criteria:**
- ✅ `ev update` reports whether a newer release exists and prints the installer URL.
- ✅ The updater never downloads or executes code automatically.
- ✅ Tray menu "Check for updates" works.
- ✅ Updater tests pass.

---

## Configuration additions

`ev.config` gained:
- `skills_dir`, `skills_auto_discover`, `enable_skills`
- `voice_enabled`, `voice_stt_backend`, `voice_tts_backend`, `voice_model_dir`

---

## Files touched

| File | Change |
|---|---|
| `src/ev/core/registry.py` | New — `RegistryBase[T]` + global `@register` decorator |
| `src/ev/core/component.py` | New — base classes for tool/agent/skill/memory/engine |
| `src/ev/core/discovery.py` | New — pkgutil auto-discovery |
| `src/ev/tools/*_tool.py` | Converted to `@register("tool", ...)` |
| `src/ev/tools/registry.py` | Thin wrapper over global registry |
| `src/ev/agents/*.py` | Registered as agents |
| `src/ev/skills/*.py` | New — skill loader, manifest parser, skill tool adapter |
| `skills/*/SKILL.md` | New — built-in prompt-based skills |
| `src/ev/voice/*.py` | New — STT/TTS backends and `VoiceManager` |
| `src/ev/sandbox/*.py` | New — sandbox policy, runner, isolated execution |
| `src/ev/tools/sandbox_tool.py` | New — auto-discovering tier-2 sandbox tool |
| `src/ev/eval/*.py` | New — eval case/suite/runner/checks/loader |
| `src/ev/secrets/store.py` | New — encrypted secrets vault |
| `src/ev/updater/checker.py` | New — read-only GitHub releases comparator |
| `src/ev/server/api.py` | Added `/voice/chat`, `/skills`, uses auto-discovered tool registry |
| `src/ev/server/chat.py` | Wired for sandbox tool; voice chat path |
| `src/ev/config.py` | Added skills and voice settings |
| `scripts/desktop_presence.py` | Unified daemon + hotkey + tray + voice loop entry point |
| `tests/test_updater.py` | New — updater tests |
| `pyproject.toml` | Added `[voice]`, `[secrets]` extras; `greenlet` in core deps |
| `.gitignore` | Added exception for `src/ev/secrets/` |

---

## Testing strategy

| Test | How |
|---|---|
| Registry auto-discovery | Import `ev.core.discovery` and assert known tools register |
| Skill loader | Load `skills/hello_ev/SKILL.md` and assert manifest + template parsed |
| Voice manager | Mock backends; assert `listen_and_transcribe()` and `say()` route correctly |
| Sandbox | Assert dangerous code is rejected; allowed code returns expected result |
| Eval runner | Run a small YAML suite against mock/live registry and assert report |
| Secrets vault | Encrypt, decrypt, and verify `.env` override behavior with mocked keyring |
| Updater | Mock GitHub API; assert update-available/up-to-date/network-error paths |
| Desktop presence | Mock subprocess/pynput/pystray; assert start/stop order and voice loop wiring |
| Full regression | `python -m pytest` remains green |

---

## Acceptance criteria

- ✅ OpenJarvis-style plugin registry/ABCs exist and all existing tools register via decorator.
- ✅ `ev skills list` and `GET /skills` expose discovered skills.
- ✅ `ev.voice` provides mock/faster-whisper STT and mock/kokoro/pyttsx3 TTS backends.
- ✅ `scripts/desktop_presence.py` runs daemon, hotkey, tray, and voice loop from one entry point.
- ✅ `POST /voice/chat` works for the desktop voice client.
- ✅ `ev.sandbox` + `SandboxTool` safely executes whitelisted code and requires tier-2 confirmation.
- ✅ `ev.eval` runner produces pass/fail reports with per-case latency.
- ✅ `ev.secrets` stores and retrieves encrypted values, overriding `.env` when loaded.
- ✅ `ev.updater` compares GitHub releases read-only and never auto-downloads.
- ✅ `python -m pytest` passes (253 passed, 1 skipped, no new skips).
- ✅ `ruff check .` clean.
- ✅ `cd web && npm run build` clean.
- ✅ README and memory files updated.

---

## Verification at completion

- `python -m pytest tests/` → **253 passed, 1 skipped**.
- `ruff check .` → clean.
- `cd web && npm run build` → clean.
- Commit `02781e2` pushed to `origin/main`.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Plugin discovery loads untrusted modules | Discovery only imports known `ev.*` packages; skills are prompt-based and do not execute arbitrary Python. |
| Voice extras are large / fail in minimal installs | Mock backend keeps CI green; extras are optional. |
| Sandbox escape | AST whitelist + subprocess isolation + timeout; dangerous builtins banned. |
| Eval suite becomes stale | Ground truth comes from seeded fixtures or explicit expected values, not live DB. |
| Secrets vault key loss | Document that losing the OS keyring or master password loses the vault; no recovery backdoor. |
| Auto-updater social-engineering | Read-only comparator; explicit user confirmation required before any download/install. |

---

## Next action

Phase G is next: Tauri desktop wrapper, cross-platform installers, file-system watcher, richer OS presence (global wake word, desktop capture, intent bridging), skill eval harness/golden datasets, cloud relay/webhook ingress, and observability/cost tracing.

- [Phase G roadmap](../assessments/2026-09-17-hi-ev-honest-state-and-roadmap.md#phase-g--tauri-desktop-wrapper-richer-os-presence-skill-evals-cloud-relay-observability-active)
