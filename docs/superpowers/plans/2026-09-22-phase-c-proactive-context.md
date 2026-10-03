# Phase C — Proactive Alerts + Persistent Context

> **Date:** 2026-09-22 (updated 2026-10-03)
> **Goal:** EV stops being purely reactive; it pushes alerts, remembers conversation threads, and surfaces what matters before it is too late.
> **Status:** ✅ COMPLETE and pushed to `origin/main` (`dff10c3`).
> **Previous phase:** [Phase B — Reasoning Router + Eval](2026-09-17-phase-b-reasoning-router-eval.md)

> **Update 2026-10-03:** Phases D, E, and F are now also complete and pushed to `origin/main` (commit `02781e2`, 253 passed / 1 skipped). Phase F added a plugin registry, skills, local voice pipeline, sandbox, eval runner, encrypted secrets vault, auto-updater, and unified `scripts/desktop_presence.py`. Phase G is next. See the [honest state assessment](../assessments/2026-09-17-hi-ev-honest-state-and-roadmap.md) and the [Phase F dossier](2026-10-03-phase-f-plugin-architecture.md) for the full current picture.

---

## Deliverables

### 1. Persistent chat threads
- `ChatThread` and `ChatTurn` ORM models in `src/ev/db/models.py`.
- Alembic migration `4aabc70a3bad_add_chat_threads_and_chat_turns.py`.
- `MemoryStore` helpers: `create_chat_thread`, `get_chat_thread`, `list_chat_threads`, `list_chat_turns`, `add_chat_turn`, `delete_chat_thread`.
- `ChatSession` accepts `thread_id`, lazy-creates/loads threads, loads the 20-turn window, and persists every user/assistant/tool/route turn.

### 2. REST thread CRUD
- `POST /threads`, `GET /threads`, `GET /threads/{id}`, `PATCH /threads/{id}`, `DELETE /threads/{id}` in `src/ev/server/api.py`.

### 3. Proactive WebSocket alerts
- `src/ev/server/api.py` `_alert_loop` queries urgent/overdue deadlines and pushes `type: alert` payloads to all active WebSockets.
- Alert categories include deadline, people, obligations, and generic system alerts.
- Respects quiet hours and `kill_switch`.

### 4. Morning brief scheduler
- `_brief_loop` wakes at `EV_MORNING_BRIEF_TIME` (default `08:00`) and pushes a daily brief over WebSocket.
- Optional Telegram relay dispatches the same brief.

### 5. Optional Telegram relay
- `src/ev/server/telegram.py` skeleton with `send`, `alert`, and `morning_brief` methods using `httpx`.
- Disabled by default; enabled via `EV_TELEGRAM_ENABLED=true`, `EV_TELEGRAM_BOT_TOKEN`, and `EV_TELEGRAM_CHAT_ID`.

### 6. Frontend panels
- `web/src/ui/Threads.tsx` — thread list, create, switch, rename, delete.
- `web/src/ui/Alerts.tsx` — proactive alert toast panel.
- `web/src/lib/bridge.ts` and `web/src/store.ts` track `threadId`, `alerts`, and `dismissAlert`.
- `web/src/index.css` adds `.alerts`, `.threads`, `.thread-row` styling.

---

## Acceptance criteria

- ✅ Chat threads persist across reconnections and page reloads.
- ✅ With browser open, an urgent deadline produces a visible HUD alert within one alert interval.
- ✅ Morning brief scheduler fires at the configured time.
- ✅ Telegram relay skeleton is wired and tested (disabled by default).
- ✅ `python -m pytest tests/` passes; `cd web && npm run build` clean.

---

## Verification at completion

- `python -m pytest tests/` → **190 passed, 1 skipped**.
- `ruff check .` → clean.
- `cd web && npm run build` → clean.
- Live end-to-end smoke test against the running daemon passed: health, thread CRUD, WebSocket connect with `?thread_id`, transcript persistence, and proactive alert push.

---

## Next action

Phase D, E, and F are complete. Phase G is next.
- [Phase D — Safe Autonomy + Desktop Presence](2026-09-22-phase-d-safe-autonomy.md)
- [Phase E — Launch MVP](2026-10-02-phase-e-launch-mvp.md)
- [Phase F — Plugin Architecture, Skills, Voice, and Auto-Updater](2026-10-03-phase-f-plugin-architecture.md)
- [Phase G roadmap](../assessments/2026-09-17-hi-ev-honest-state-and-roadmap.md#phase-g--tauri-desktop-wrapper-richer-os-presence-skill-evals-cloud-relay-observability-active)
