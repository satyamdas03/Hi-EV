# Phase E Launch MVP — Local Installer + Setup Wizard

> **Date:** 2026-10-02
> **Goal:** Ship a launch-ready, local-only Hi-EV that a non-technical client can download, install, and run on Windows without writing `.env` files or opening a terminal.
> **Scope:** Local installer only. No hosted cloud preview (preserves the local-first/personal-only boundary).

---

## 1. What "launch-ready" means

A client should be able to:

1. Download `Hi-EV-Setup.exe` (or a portable `Hi-EV.exe`).
2. Run it.
3. See an in-browser setup wizard on first run.
4. Fill in a few fields (notes path, optional API keys, blocked handles/domains).
5. Click a button to finish setup.
6. Use the HUD by voice or text with local memory working.

Everything stays on their machine. No cloud brain, no hosted preview.

---

## 2. Explicitly out of scope for v1.0

These remain on the Phase E v1.1 roadmap:

- Local STT/TTS (faster-whisper / Piper / Kokoro)
- Tool self-authoring loop
- OS keyring / encrypted secrets store
- Cloud relay / Telegram beyond the existing skeleton
- macOS / Linux installers
- Auto-updater
- `ev why` audit query tool

---

## 3. Work streams

### Stream 1 — Unified desktop entry point

**New file:** `scripts/desktop_presence.py`

Responsibilities:

1. Determine the application data directory (`%LOCALAPPDATA%\Hi-EV` on Windows).
2. Locate or create `.env` in that directory.
3. Start the FastAPI daemon as a managed subprocess (`python -m evd` or the bundled equivalent).
4. Wait for `GET /health` to return OK.
5. Start the global hotkey listener (`pynput`) in a background thread.
6. Start the system tray icon (`pystray`) in a background thread.
7. Open the default browser to `http://127.0.0.1:7345`.
8. On tray exit / SIGINT: gracefully stop subprocesses and exit.

**Key design decisions:**

- The daemon is started as a subprocess so the desktop entry point does not block the GUI thread and so the tray icon can monitor/restart it.
- `.env` lives in `%LOCALAPPDATA%\Hi-EV\.env`, not the install directory. This allows per-user config and clean upgrades.
- The desktop entry point also serves as the launcher that the Windows installer shortcut points to.

**Configuration additions in `src/ev/config.py`:**

- `desktop_auto_open_hud: bool = True`
- `desktop_data_dir: Path` derived from platform

### Stream 2 — First-run setup wizard

**New backend module:** `src/ev/server/setup.py`

Responsibilities:

- `GET /setup` returns whether first-run setup is needed:
  - `.env` missing or empty
  - Required fields missing (`notes_path`, at least one LLM provider key for chat)
- `POST /setup` accepts JSON, validates paths/keys, writes `.env`, and returns `{"restart_required": true}`.

**Fields collected:**

| Field | Required | Default |
|---|---|---|
| `notes_path` | yes | `%USERPROFILE%\notes` |
| `llm_provider` | yes | `nvidia` |
| `nvidia_api_key` | no* | — |
| `anthropic_api_key` | no* | — |
| `openai_api_key` | no* | — |
| `github_token` | no | — |
| `blocked_handles` | no | `[]` |
| `blocked_domains` | no | `[]` |
| `quiet_start` | no | `22:00` |
| `quiet_end` | no | `08:00` |

*At least one LLM provider key is required for full chat. Without it, the HUD enters a read-only/fallback mode and the wizard shows a warning.

**New frontend component:** `web/src/ui/SetupWizard.tsx`

- Centered modal overlay that blocks the HUD until setup is complete.
- Form fields with validation messages.
- Test-connection button for the selected LLM provider.
- Submit button writes config and shows a restart countdown.
- App.tsx conditionally renders `SetupWizard` when `/setup` reports `needs_setup: true`.

**API additions in `src/ev/server/api.py`:**

- `GET /setup` and `POST /setup` endpoints.
- These endpoints must work even when the LLM client would otherwise fail due to missing keys.

### Stream 3 — Windows installer build

**New file:** `scripts/build_installer.py`

Responsibilities:

1. Verify `web/dist/` exists (run `npm run build` if needed).
2. Run PyInstaller with a spec that bundles:
   - Python runtime
   - `src/ev/` package
   - `web/dist/` static assets
   - `scripts/desktop_presence.py` as the entry point
   - All core dependencies from `pyproject.toml`
   - Optional desktop dependencies (`pynput`, `pystray`, `Pillow`)
3. Copy `.env.example` into the bundle as a template.
4. Produce `dist/Hi-EV/` directory or `dist/Hi-EV.exe`.

**PyInstaller approach:**

- Use a generated `.spec` file for control over datas/binaries/hidden imports.
- Hidden imports: `sqlite_vec`, `aiosqlite`, `pgvector`, `pydantic`, `fastapi`, `uvicorn`, all `ev.*` submodules.
- Datas: `web/dist/`, `.env.example`, Alembic migration files.
- Console mode initially so we can see startup errors; switch to `--windowed` once stable.

**MVP deliverable:**

- A single portable `Hi-EV.exe` that clients can run directly.
- A proper NSIS/MSI installer can be added in v1.1 if needed.

### Stream 4 — Graceful missing-key fallback

**Changes in `src/ev/llm/client.py`:**

- Raise `LLMClientError` with a clear message when no provider key is configured.
- Keep the error message free of secrets.

**Changes in `src/ev/server/chat.py`:**

- Catch `LLMClientError` during intent classification and chat completion.
- If the error is due to missing configuration, return a friendly message pointing the user to the setup wizard.
- Do not crash the WebSocket session.

**Changes in `web/src/ui/Diagnostics.tsx`:**

- Add rows for:
  - `.env` location
  - LLM provider key status (configured / missing)
  - Database path

### Stream 5 — Documentation and memory

- Update `README.md` with:
  - Windows download link placeholder
  - First-run setup instructions
  - Troubleshooting section
- Create `docs/superpowers/plans/2026-10-02-phase-e-launch-mvp.md` (this document).
- Create memory file `C:\Users\point\.claude\projects\C--Users-point-projects-Hi-EV\memory\hi-ev-phase-e-launch-mvp.md`.
- Update `MEMORY.md` index.

---

## 4. Files touched

| File | Change |
|---|---|
| `scripts/desktop_presence.py` | New — unified launcher |
| `scripts/build_installer.py` | New — PyInstaller build script |
| `src/ev/config.py` | Add desktop/data-dir settings |
| `src/ev/server/api.py` | Add `/setup` endpoints |
| `src/ev/server/setup.py` | New — setup validation and `.env` writer |
| `src/ev/llm/client.py` | Better missing-key error |
| `src/ev/server/chat.py` | Graceful LLM error handling |
| `web/src/config.ts` | Optional setup API URL override |
| `web/src/App.tsx` | Conditionally render setup wizard |
| `web/src/store.ts` | Add setup-needed state |
| `web/src/lib/bridge.ts` | Add setup status message type |
| `web/src/ui/SetupWizard.tsx` | New — first-run wizard |
| `web/src/ui/Diagnostics.tsx` | Add env/db/llm status rows |
| `web/src/index.css` | Wizard styles |
| `tests/test_setup.py` | New — backend setup tests |
| `tests/test_desktop_presence.py` | New — mocked launcher tests |
| `pyproject.toml` | Add PyInstaller / build deps, console script |
| `README.md` | Installer instructions |

---

## 5. Testing strategy

| Test | How |
|---|---|
| Backend setup validation | `tests/test_setup.py` with mocked filesystem and env writes |
| Setup endpoint | ASGI transport against `/setup` GET/POST |
| Missing-key fallback | Mock `LLMClient` to raise `LLMClientError` in chat handler |
| Desktop presence orchestration | Mock `subprocess.Popen`, `pystray`, `pynput`; assert start/stop order |
| Frontend wizard | TypeScript build must pass; visual flow tested manually |
| Build script | Run `python scripts/build_installer.py --smoke-test` to verify bundled exe starts |
| Full regression | `python -m pytest` must remain green |

---

## 6. Acceptance criteria

- [ ] `python scripts/build_installer.py` produces a runnable `dist/Hi-EV.exe`.
- [ ] Running `Hi-EV.exe` on a clean Windows machine opens the browser to the setup wizard if `.env` is missing.
- [ ] Setup wizard writes `.env`, restarts the daemon, and the HUD becomes usable.
- [ ] Without an LLM key, the HUD shows a friendly read-only/fallback message instead of crashing.
- [ ] Tray icon, global hotkey (`Ctrl+Alt+E`), and wake word still work.
- [ ] `python -m pytest` passes (target: 197+ passed, 1 skipped, no new skips).
- [ ] `ruff check .` clean.
- [ ] `cd web && npm run build` clean.
- [ ] README and memory files updated.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| PyInstaller bundle too large or fails on Windows | Build on Windows with `--onedir` first; iterate on hidden imports |
| `sqlite-vec` extension fails inside PyInstaller | Bundle the `.dll`/`.so` explicitly; test on a clean VM |
| Missing API key causes daemon crash before wizard | Make `/setup` endpoints not require LLM client; lazy-load keys |
| `.env` location confusion | Use `%LOCALAPPDATA%\Hi-EV` consistently; show path in diagnostics |
| Browser not opening | Add tray menu item "Open HUD" as fallback |
| Antivirus false positive on PyInstaller exe | Code-signing in v1.1; for MVP, document the publisher |

---

## 8. Next actions (implementation order)

1. **Stream 2 first** — setup wizard backend + frontend. This unblocks everything else because it removes the manual `.env` requirement.
2. **Stream 1** — desktop presence entry point.
3. **Stream 4** — graceful missing-key fallback.
4. **Stream 3** — PyInstaller build script.
5. **Stream 5** — docs and memory updates.
6. **Final verification** — full test suite, build, and manual smoke test.
