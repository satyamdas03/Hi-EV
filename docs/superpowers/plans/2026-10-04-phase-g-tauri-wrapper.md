# Phase G — Tauri Desktop Wrapper (first stream)

> **Date:** 2026-10-04
> **Goal:** Wrap the existing Hi-EV web face and Python daemon in a native Tauri v2 desktop shell, replicating the current `scripts/desktop_presence.py` entry point (daemon launch, system tray, global hotkey) in a cross-platform, AV-friendly package.
> **Scope:** Native desktop shell only. Other Phase G streams (file-system watcher, skill evals, cloud relay, observability) will follow in later sprints.
> **Status:** ✅ SKELETON COMPLETE — `cargo check`, `cargo clippy`, `python -m pytest`, `ruff check .`, and `npm run tauri:build` all pass. Windows MSI installer produced.

---

## 1. What we are building

A Tauri v2 app in a new `desktop/` directory that:

1. Embeds the existing Vite React/Three.js HUD from `web/dist/` in a native webview window.
2. Spawns and monitors the local Hi-EV Python daemon.
3. Provides a native system tray icon with menu actions:
   - Show / Hide EV
   - Start / Stop daemon
   - Open settings (launches setup wizard in-app)
   - Voice push-to-talk (global shortcut)
   - Quit
4. Registers a global shortcut (`Ctrl+Alt+E` on Windows/Linux, `Cmd+Shift+E` on macOS) that brings EV to the foreground and starts a voice turn.
5. Ships cross-platform installers (Windows `.msi`/`.exe`, macOS `.dmg`, Linux `.AppImage`/`.deb`).

The existing `scripts/desktop_presence.py` PyInstaller bundle remains available as a fallback during Phase G. Tauri becomes the recommended primary install path.

---

## 2. Key architectural decisions

### 2.1 Python daemon handling — recommended: system Python + setup wizard

- The Tauri installer will **not** bundle a full Python runtime.
- On first run, the built-in setup wizard detects whether Python >=3.12 is available.
- If Python is missing, the wizard shows a download/install link and refuses to proceed.
- If Python is present, Tauri launches the daemon with:
  - Dev: `python -m evd` from the repo venv
  - Prod: `python -m pip install hi-ev` (or local wheel) + `python -m evd`
- Rationale: avoids the antivirus false-positics that bundled PyInstaller EXEs trigger, keeps installers small (~50-80MB), and matches the existing setup-wizard flow.

### 2.2 Tauri project layout

```
Hi-EV/
  web/                          # existing Vite React app
    package.json
    vite.config.ts
    src/...
    dist/                       # build output consumed by Tauri
  desktop/                      # new Tauri v2 project
    package.json                # Tauri scripts + dev dependencies
    src-tauri/
      Cargo.toml                # Rust deps: tauri, tray, global-shortcut, notification, shell
      tauri.conf.json           # points frontend distDir to ../web/dist
      capabilities/
        default.json            # permissions: shell, tray, global-shortcut, notification, window
      icons/                    # Hi-EV app icons
      src/
        main.rs                 # app entry: daemon process manager, tray, shortcuts
        daemon.rs               # spawn / health-check / stop Python daemon
        tray.rs                 # tray icon + menu handlers
        shortcut.rs             # global shortcut registration
        lib.rs                  # public Rust API / command modules
    src/                        # (optional) thin TypeScript bridge if web needs native APIs
  scripts/
    build_tauri.py              # build web + Tauri + package installers
```

### 2.3 Frontend changes

Minimal. The React app already points at `ws://127.0.0.1:7345/ws` and `http://127.0.0.1:7345` via `web/src/config.ts`.

- Add a small Tauri-specific bridge (`web/src/lib/tauri.ts`) that:
  - Detects `window.__TAURI__` presence.
  - Exposes `invoke('show_window')`, `invoke('hide_window')`, `invoke('daemon_status')` for native integration.
- No change to the existing browser path; the HUD still works in a normal browser for development.

### 2.4 Daemon lifecycle

- Tauri starts the daemon on app launch (unless `EV_DAEMON_AUTO_START=false`).
- Polls `/health` every 250ms until ready, then shows the HUD.
- If the daemon crashes, show a native notification and offer to restart.
- On quit, terminate the daemon child process gracefully.

---

## 3. Implementation tasks

| # | Task | Files / commands | Status |
|---|------|------------------|--------|
| 1 | Create Tauri v2 project skeleton | `desktop/package.json`, `desktop/src-tauri/Cargo.toml`, `tauri.conf.json`, `capabilities/default.json` | ✅ `cargo check` clean |
| 2 | Configure Tauri to load `web/dist` | `desktop/src-tauri/tauri.conf.json` `build.frontendDist` | ✅ `npm run tauri:build` finds assets |
| 3 | Add app icons | `desktop/src-tauri/icons/` | ✅ Placeholder icons generated |
| 4 | Implement daemon spawn + health check | `desktop/src-tauri/src/daemon.rs`, `lib.rs` | ✅ Spawns `python -m evd`, polls `/health` |
| 5 | Implement system tray | `desktop/src-tauri/src/tray.rs` | ✅ Show/Hide, daemon start/stop, Settings, Quit |
| 6 | Implement global shortcut | `desktop/src-tauri/src/shortcut.rs` | ✅ `Ctrl+Alt+E` / `Cmd+Shift+E` registered |
| 7 | Add native notification support | use Tauri `notification` plugin | 🚧 Plugin wired; notifications not yet emitted from daemon events |
| 8 | Frontend Tauri bridge | `web/src/lib/tauri.ts` | ✅ Detects native mode, listens for shortcut event |
| 9 | Build orchestration script | `scripts/build_tauri.py` | ✅ Builds web + Tauri release |
| 10 | Cross-platform CI smoke test | add to `README.md` / docs | 🚧 Windows MSI verified; macOS/Linux pending |
| 11 | Documentation + memory update | `README.md`, memory files | ✅ Updated |

---

## 4. Build and run flow

### Development

```bash
# Terminal 1: run the Python daemon
cd /c/Users/point/projects/Hi-EV
python -m evd

# Terminal 2: build the web face
cd web
npm run build

# Terminal 3: run Tauri in dev mode (webview reloads on changes)
cd ../desktop
npm install
npm run tauri dev
```

### Production build

```bash
cd /c/Users/point/projects/Hi-EV
python scripts/build_tauri.py
# Output:
#   desktop/src-tauri/target/release/bundle/msi/Hi-EV_0.1.0_x64_en-US.msi
#   desktop/src-tauri/target/release/bundle/dmg/Hi-EV_0.1.0_x64.dmg
#   desktop/src-tauri/target/release/bundle/appimage/Hi-EV_0.1.0_x64.AppImage
```

---

## 5. Verification criteria

- `cd web && npm run build` still passes.
- `python -m pytest` still passes (253 passed, 1 skipped).
- `ruff check .` still clean.
- `cd desktop && cargo check` and `cargo clippy` clean.
- Tauri app launches on Windows and macOS (Linux if available), shows the HUD, and connects to the daemon.
- Global shortcut focuses the window.
- System tray can hide/show and quit the app.
- Quitting Tauri terminates the daemon child process.

---

## 6. Out of scope for this stream

These remain for later Phase G sprints after the Tauri shell is merged:

- File-system watcher (moved to next stream).
- Global wake word outside the browser.
- Desktop screenshot ingestion.
- Cloud relay / webhook ingress.
- Skill eval harness golden datasets.
- Observability / cost tracing / `ev why`.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Tauri build fails on Windows without WebView2 | Document WebView2 runtime requirement; installer can bundle it. |
| macOS notarization / code signing | Use ad-hoc signing for CI; document paid cert for release. |
| Antivirus still flags Tauri installer | Keep installer small, avoid bundling Python, sign binaries when possible. |
| Daemon does not terminate cleanly on quit | Use Tauri `RunEvent::Exit` to kill child process; add timeout + `kill()` fallback. |
| Global shortcut conflicts | Make shortcut configurable via `.env`; default avoids common OS shortcuts. |

---

## 8. Recommended first step after approval

Create the Tauri project skeleton and configure it to load `web/dist`, then implement daemon spawning and a basic tray menu. Get a window showing the HUD before adding shortcuts and notifications.
