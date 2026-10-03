# Phase D — Safe Autonomy + Desktop Presence

> **Date:** 2026-09-22 (updated 2026-10-03)
> **Goal:** EV can act on T1 reliably and confirm T2 safely; it lives outside the browser.
> **Status:** ✅ COMPLETE and pushed to `origin/main` (`92ff90d` for original Phase D; `02781e2` for Phase F refresh). Live smoke test passed against the daemon on `127.0.0.1:7345`.
> **Previous phase:** [Phase C — Proactive Alerts + Persistent Context](2026-09-22-phase-c-proactive-context.md)

> **Update 2026-10-03:** The desktop presence scripts were consolidated into a single `scripts/desktop_presence.py` entry point in Phase F (commit `02781e2`). Phase F also added local voice, skills, sandbox, eval runner, encrypted secrets, and a read-only auto-updater. Phases E and F are complete. Phase G is next. See the [honest state assessment](../assessments/2026-09-17-hi-ev-honest-state-and-roadmap.md) and the [Phase F dossier](2026-10-03-phase-f-plugin-architecture.md) for the full current picture.

---

## Deliverables

### 1. T2 confirmation flow
- `src/ev/server/chat.py` `ChatSession` pauses on T2 tools, sends `type: confirm` over WebSocket, and waits for `confirm_response`.
- Confirmed actions run via `_run_confirmed_tool`; denied actions return a cancellation message.
- A new user transcript cancels any outstanding confirmation.
- Tool tiers promoted: `work_on`, `draft_commit`, `draft_pr`, `draft_reply` → T2; `remember` → T1; all read-only tools remain T0.

### 2. T3 hard blocks
- T3 tools are refused immediately in the web/voice interface with a permanent-block message.
- The guard already blocks tier-downgrade requests and work-boundary violations; untrusted content caps effective tier automatically.

### 3. Frontend confirmation UX
- `web/src/ui/ConfirmModal.tsx` blocking modal with Confirm/Deny buttons and voice hint.
- `web/src/store.ts` tracks `pendingConfirmation` and `focusRequested`.
- `web/src/lib/voice.ts` supports voice confirm/deny while a confirmation is pending.
- `web/src/lib/bridge.ts` adds `confirm`, `confirm_response`, and `focus` message types.

### 4. CLI confirmation
- `src/ev/cli/main.py` T2 commands (`work on`, `draft commit`, `draft pr`, `draft reply`) require `--yes` / `-y` or an interactive `click.confirm`.

### 5. Desktop presence
- `POST /focus` endpoint in `src/ev/server/api.py` pushes `type: focus` to all active WebSockets.
- `scripts/global_hotkey.py` uses `pynput` to listen for `Ctrl+Alt+E` and hit `/focus`.
- `scripts/tray_widget.py` uses `pystray` + `Pillow` to show a system-tray EV icon with Open HUD / Focus / Exit menu.
- `web/src/lib/voice.ts` adds a continuous wake-word listener (`startWakeListening`) that triggers normal listening on "hey ev".
- `web/src/App.tsx` subscribes to phase changes and starts/stops wake listening when dormant.

### 6. Configuration
- `src/ev/config.py` adds `base_url`, `global_hotkey_enabled`, `global_hotkey_combo`, `tray_widget_enabled`, `wake_word_enabled`, `wake_word_phrase`.
- `pyproject.toml` adds optional `[desktop]` dependencies: `pynput`, `pystray`, `Pillow`.

### 7. Tests
- `tests/test_chat_handler.py` covers T1 auto-run, T2 confirmation request, confirm/deny response, and T3 hard block.
- `tests/test_cli.py` updated for `--yes` requirement and interactive confirmation.
- `tests/test_server.py` adds `/focus` endpoint test.
- `tests/test_draft_tools.py` updated for tier 2.
- Fixed pre-existing ruff issues in `tests/test_chat_threads.py` and `tests/test_proactive_alerts.py`.

### 8. Repo hygiene fix
- `.gitignore` had a bare `lib/` pattern that ignored `web/src/lib/`, meaning the voice/bridge/audio/TTS/VAD source files from Phases B and C were never tracked. Changed to `/lib/` (root-only) so the frontend core source is now in git.

---

## Acceptance criteria

- ✅ A T2 tool request stops at `type: confirm` and shows exact payload; confirming runs the action, denying cancels it.
- ✅ Destructive/high-risk intents are refused regardless of prompt or voice command.
- ✅ Hotkey (`Ctrl+Alt+E`) activates EV from any app; browser wake word ("hey ev") triggers listening.
- ✅ CLI T2 commands require explicit confirmation unless `--yes` is passed.
- ✅ `python -m pytest tests/` passes; `ruff check .` clean; `cd web && npm run build` clean.

---

## Verification at completion

- `python -m pytest tests/` → **197 passed, 1 skipped**.
- `ruff check .` → clean.
- `cd web && npm run build` → clean.
- Commit `92ff90d` pushed to `origin/main`.
- Live smoke test `e2e_phase_d.py` passed against the daemon on `127.0.0.1:7345`:
  - Health endpoint OK.
  - T2 `work_on` request paused and emitted `type: confirm`.
  - Confirm response advanced through `phase: acting`, returned a delta, and emitted `done`.
  - Deny response returned a cancellation delta and `done`.
  - Destructive request handled gracefully without crash.
  - `POST /focus` notified the connected WebSocket client with `type: focus`.

---

## Remaining polish (Phase E/F resolution)

The following items were deferred to later phases and are now shipped:

- ✅ **Package the tray widget / global hotkey as a single desktop entry point.** Shipped in Phase F as `scripts/desktop_presence.py`, which launches the daemon, global hotkey, system tray, and (when voice is enabled) a local voice loop.
- ✅ **Replace browser SpeechRecognition with a local STT model.** Shipped in Phase F via `ev.voice` with faster-whisper, kokoro, pyttsx3, and mock backends; `scripts/desktop_presence.py` uses `VoiceManager` for the hotkey voice loop.

---

## Next action

Phases E and F are complete. Phase G is next.
- [Phase E — Launch MVP](2026-10-02-phase-e-launch-mvp.md)
- [Phase F — Plugin Architecture, Skills, Voice, and Auto-Updater](2026-10-03-phase-f-plugin-architecture.md)
- [Phase G roadmap](../assessments/2026-09-17-hi-ev-honest-state-and-roadmap.md#phase-g--tauri-desktop-wrapper-richer-os-presence-skill-evals-cloud-relay-observability-active)
