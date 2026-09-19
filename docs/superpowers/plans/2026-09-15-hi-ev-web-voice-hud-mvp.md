# Hi-EV Web / Voice / HUD MVP — Port JARVIS Frontend to Hi-EV Backend

> **Goal:** Give Hi-EV a voice-first, holographic web face by porting the JARVIS React/Three.js shell and wiring it to the existing Hi-EV FastAPI backend. This is intentionally an MVP: browser speech APIs for STT/TTS, a push-to-talk trigger, and a simplified reactor/HUD. Local wake-word, Kokoro TTS, and full blade panels come later.

## Why now

The Hi-EV backend is solid through Phase 3 (82 tests passing, Gmail/Calendar live, daemon on `127.0.0.1:7345`). The missing piece is the interface layer described in the README: voice loop, system-tray/desktop widget, and proactive alerts. JARVIS (`https://github.com/adewaskar/jarvis.git`) already built exactly this — a polished browser-native voice assistant with a Three.js reactor HUD — but it is hard-wired to the Claude Code bridge. We reuse its frontend shell and discard its Node/Claude bridge, connecting it to Hi-EV's Python daemon instead.

## Scope

### In scope for this MVP
- New `web/` directory with Vite + React + TypeScript.
- Ported, simplified JARVIS visual shell:
  - Boot / ignition sequence.
  - Three.js reactor scene (Core + Particles, no orbits for MVP).
  - HUD: status text, transcript log, suggestion strip, diagnostics overlay.
- Voice loop in the browser:
  - `SpeechRecognition` (STT).
  - `speechSynthesis` (TTS).
  - Push-to-talk (`Space`) and click-to-talk.
  - Barge-in / abort on new user speech.
- WebSocket connection to Hi-EV daemon:
  - Browser sends transcript.
  - Backend routes utterance to the right Hi-EV tool via LLM-based intent classification.
  - Text response streamed back and spoken.
- Backend changes:
  - CORS for `localhost:5173`.
  - `/ws` WebSocket endpoint.
  - `ChatHandler` with per-connection state and tool dispatch.
- Tests for the WebSocket endpoint and chat handler.

### Out of scope for this MVP (tracked for follow-up)
- True wake word (Porcupine/openWakeWord).
- Local STT (faster-whisper).
- Local TTS (Piper / Kokoro).
- Media proxy / SSRF-safe page rendering.
- Model-authored HTML blades/panels.
- Hand tracking / touchless gestures.
- Persistent chat history (planned in Phase C).
- Server-initiated proactive alerts over WebSocket (planned in Phase C).

## Post-MVP updates

- **Streaming response UI (Phase B):** `web/src/ui/Chat.tsx` now renders streaming deltas with an animated caret, phase badge, and a stop button; backend supports `type: stop` abort.

## Order of work

### 1. Backend scaffold: CORS + WebSocket endpoint
**Why first:** The frontend cannot connect until the backend accepts WebSocket and CORS.

- Add `fastapi.middleware.cors.CORSMiddleware` to `src/ev/server/api.py` for `http://localhost:5173` and `http://127.0.0.1:5173`.
- Add `from fastapi import WebSocket, WebSocketDisconnect`.
- Add `/ws` route that accepts connections, stores them in `app.state.active_connections`, and echoes a heartbeat.
- Define a WebSocket message envelope: `{ "type": "transcript", "text": "..." }`, `{ "type": "delta", "text": "..." }`, `{ "type": "done" }`, `{ "type": "error", "message": "..." }`.
- **Tests:** `tests/test_server.py` — connect, send `{"type":"ping"}`, expect `pong`; disconnect cleanly.

### 2. Backend chat / intent handler
**Why second:** Once the socket exists, we need something on the other end that turns speech into Hi-EV tool calls.

- Create `src/ev/server/chat.py`:
  - `ChatSession` class per WebSocket connection.
  - Maintain a short rolling message history (system + last N turns).
  - `classify_intent(text: str) -> Intent` using the existing `LLMClient` and a small prompt that maps utterances to known tool names, or falls back to a direct LLM Q&A if no tool matches.
  - Known intents: `status`, `brief`, `research`, `deadlines`, `alerts`, `people`, `obligations`, `prep`, `work`, `draft`, `chat`.
  - For tool intents, extract parameters with a lightweight LLM prompt or regex fallback, then call the same `ToolRegistry` + tools used by REST endpoints.
  - For `chat`, answer from general knowledge using `LLMClient`.
  - Stream the final response to the WebSocket as `{type: "delta", text: "..."}` chunks. ✅ Done; fast chat now streams word-by-word.
  - Handle `type: stop` to abort an in-progress stream and emit `done`. ✅ Done.
- Register the chat handler in `src/ev/server/api.py` lifespan so sessions can be cleaned up on shutdown.
- **Tests:** mock `LLMClient` and tool runs; assert `ChatSession` emits correct tool result as a WebSocket message.

### 3. Frontend package scaffold
**Why third:** We need the build tooling before we can port components.

- Create `web/package.json` with:
  - `react`, `react-dom`, `@types/react`, `@types/react-dom`
  - `vite`, `@vitejs/plugin-react`, `typescript`
  - `zustand`, `framer-motion`, `three`, `@react-three/fiber`, `@react-three/postprocessing`
- Create `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`.
- Add minimal global styles in `web/src/index.css`.
- Add `npm run dev` / `npm run build` / `npm run preview` scripts.
- Add `web/` to `.gitignore` node_modules only; keep source in git.

### 4. Port core frontend state and bridge
**Why fourth:** Everything else depends on the store and the WebSocket client.

- `web/src/config.ts`:
  - `EV_WS_URL = import.meta.env.VITE_EV_WS_URL ?? 'ws://127.0.0.1:7345/ws'`
  - `EV_API_URL = import.meta.env.VITE_EV_API_URL ?? 'http://127.0.0.1:7345'`
- `web/src/store.ts` (Zustand):
  - Phases: `offline`, `boot`, `dormant`, `listening`, `thinking`, `speaking`, `error`.
  - `turns`: `{id, role, text}[]`.
  - `caption`, `level` (mic level 0..1), `connected`, `error`.
  - Actions: `addUserTurn`, `addJarvisDelta`, `setPhase`, `setConnected`, etc.
- `web/src/lib/bridge.ts`:
  - WebSocket client with auto-reconnect.
  - Sends transcripts; receives deltas/done/error.
  - Exposes `sendTranscript(text)`, `cancel()`, `onDelta(cb)`, `onDone(cb)`.

### 5. Port voice loop (browser APIs)
**Why fifth:** Voice is the headline feature; browser APIs get us there without native deps.

- `web/src/lib/audio.ts`: shared `MediaStream` + `AnalyserNode` + mic level publisher.
- `web/src/lib/vad.ts`: simple energy-based VAD that emits speech segments. Keep it small for MVP.
- `web/src/lib/voice.ts`:
  - Push-to-talk or click: hold `Space` → `listening` phase → VAD/recognition → emit transcript → `thinking` → send to bridge.
  - Uses `window.SpeechRecognition` / `window.webkitSpeechRecognition` with `continuous: false`, `interimResults: true`.
  - Handles `onresult`, `onerror`, `onend`.
- `web/src/lib/tts.ts`:
  - Sentence-splitting TTS queue using `speechSynthesis`.
  - Calls `window.speechSynthesis.speak(utterance)` with a selected system voice.
  - Supports `stop()` for barge-in.

### 6. Port visual shell
**Why sixth:** The reactor + HUD makes the demo compelling.

- `web/src/scene/Scene.tsx` + `web/src/scene/Core.tsx` + `web/src/scene/Particles.tsx`:
  - Port JARVIS shader-based reactor and particle shell.
  - Drive `spin`, `level`, `color` from the Zustand store phase and mic level.
  - Skip orbits and hand pointer for MVP.
- `web/src/ui/Boot.tsx` + `web/src/ui/Ignition.tsx`: Iron Man boot sequence and click-to-power-on gate.
- `web/src/ui/Hud.tsx`: status text, transcript log, suggestion strip, mic meter.
- `web/src/ui/Diagnostics.tsx`: press `D` to show STT/TTS/connection state.
- `web/src/App.tsx`: mount scene + HUD, orchestrate phase machine, bind keyboard (`Space`, `D`).

### 7. Integration and smoke test
**Why last:** Prove the two halves talk.

- Start backend: `python -m evd`.
- Start frontend: `cd web && npm run dev`.
- Open `http://localhost:5173`, click ignition, press Space, say "status of Hi-EV".
- Expected: backend classifies intent → `StatusTool` → response streamed → TTS speaks it.
- Add a small `scripts/smoke_web.py` that opens the WebSocket, sends a transcript, and checks a non-empty response arrives.

### 8. Tests and quality
- Backend: extend `tests/test_server.py` with WebSocket cases.
- Backend: add `tests/test_chat_handler.py` for intent classification and tool dispatch (mock LLM + mock tools).
- Frontend: add `web/package.json` lint/typecheck scripts; run `npm run build` in CI.
- Run full `python -m pytest` and `ruff check src tests scripts` before declaring done.

## Files to create / modify

### New files
- `web/package.json`
- `web/tsconfig.json`
- `web/vite.config.ts`
- `web/index.html`
- `web/src/index.css`
- `web/src/main.tsx`
- `web/src/App.tsx`
- `web/src/config.ts`
- `web/src/store.ts`
- `web/src/lib/bridge.ts`
- `web/src/lib/audio.ts`
- `web/src/lib/vad.ts`
- `web/src/lib/voice.ts`
- `web/src/lib/tts.ts`
- `web/src/scene/Scene.tsx`
- `web/src/scene/Core.tsx`
- `web/src/scene/Particles.tsx`
- `web/src/ui/Boot.tsx`
- `web/src/ui/Ignition.tsx`
- `web/src/ui/Hud.tsx`
- `web/src/ui/Diagnostics.tsx`
- `web/src/ui/Suggestions.tsx`
- `src/ev/server/chat.py`
- `tests/test_chat_handler.py`
- `docs/superpowers/plans/2026-09-15-hi-ev-web-voice-hud-mvp.md` (this file)

### Modified files
- `src/ev/server/api.py` — CORS, `/ws`, chat handler wiring, `app.state` connection tracking.
- `tests/test_server.py` — add WebSocket tests.
- `.gitignore` — add `web/node_modules`, `web/dist`.
- `.env.example` — add optional `VITE_EV_WS_URL` / `VITE_EV_API_URL` documentation (or document in README).

## Acceptance criteria

1. `python -m pytest` passes (including new WebSocket/chat tests).
2. `ruff check src tests scripts` is clean.
3. `cd web && npm install && npm run build` succeeds with no TypeScript errors.
4. Running `python -m evd` and `cd web && npm run dev` together allows:
   - Clicking INITIALISE on `localhost:5173`.
   - Pressing Space, speaking "status of Hi-EV", and hearing a synthesized status response.
   - Seeing the reactor animate through `boot → dormant → listening → thinking → speaking → dormant`.
5. The WebSocket only accepts connections from `localhost:5173` / `127.0.0.1:5173` via origin check (CORS + WebSocket `origin` header).
6. No secrets or API keys are committed in `web/` source.

## Security notes

- WebSocket is local-only (`127.0.0.1:7345`).
- Tool tiers are preserved: the chat handler only auto-executes T0/T1 tools. If a user asks for a T2 action, the response must ask for confirmation; T3 actions are refused in the handler.
- Browser STT/TTS runs entirely locally; no audio leaves the machine except as text over the local WebSocket.
- The frontend has no access to `.env` secrets; it only talks to the local daemon.

## Follow-up work (post-MVP)

- True wake word (Porcupine WASM) replacing push-to-talk.
- Local faster-whisper STT + Piper/Kokoro TTS.
- Server-initiated proactive alerts over WebSocket.
- Model-authored HTML panels/blades with a Python sanitiser.
- SSRF-safe media proxy in Python for images and article reader mode.
- Hand tracking and touchless gestures.
- Persistent conversation history in Postgres.
