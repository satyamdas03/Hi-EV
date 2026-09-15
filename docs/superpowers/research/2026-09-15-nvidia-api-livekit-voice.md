# Research: NVIDIA NIM API + LiveKit voice options for Hi-EV

## NVIDIA NIM API — confirmed usable

The `nvapi-...` key you provided works with the NVIDIA NIM API Catalog at `https://integrate.api.nvidia.com/v1`.

### Authentication
- Header: `Authorization: Bearer <nvapi-key>`
- The API is **OpenAI-compatible** at the SDK level. We can use `openai.OpenAI(base_url=..., api_key=...)` or raw `httpx`.

### Chat completions
- Endpoint: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- Example model IDs from the catalog:
  - `meta/llama-3.3-70b-instruct`
  - `nvidia/llama-3.1-70b-instruct`
  - `openai/gpt-oss-120b`
  - `deepseek-ai/deepseek-v4-flash-0731`
  - `nvidia/nemotron-3.5-lightning-30b-a3b`
- Parameters match OpenAI: `messages`, `temperature`, `top_p`, `max_tokens`, `stream`, `tools`, `tool_choice`.
- Free trial credits are available; after they run out there is a quota of 100 req/min/IP with a 24-hour account cap.

### Embeddings
- Endpoint: `POST https://integrate.api.nvidia.com/v1/embeddings`
- Example model IDs:
  - `nvidia/nv-embed-v1`
  - `nvidia/nv-embedqa-e5-v5`
  - `nvidia/nemotron-3-embed-1b`
- Some models require `input_type: query | passage`; others accept the suffix `-query` / `-passage` in the model name.

### Recommendation for Hi-EV
Use NVIDIA NIM as the **primary LLM backend** for Phase 2 instead of Anthropic/OpenAI. It is free to start and OpenAI-compatible, so we only need one thin client. We will keep an optional `EV_LLM_PROVIDER` setting so you can switch to Anthropic later if you prefer.

## LiveKit voice options — research summary

LiveKit is a real-time audio/video transport framework. For a desktop assistant there are two practical paths:

### Path A: LiveKit Agents (headless / server-style)
- `livekit-agents` Python SDK
- Pipeline: STT → LLM → TTS
- Plugins exist for local FasterWhisper STT and Piper/Orpheus TTS
- Best for: always-on voice agent, but adds network complexity because LiveKit is designed around rooms/servers
- Overkill for a purely local hotkey assistant

### Path B: RoomKit UI / custom desktop app (recommended for later)
- `roomkit-live/roomkit-ui` is a PySide6 desktop voice assistant with global hotkey, system tray, VU meter, local STT/TTS, and MCP tools
- Best match for the "open laptop" experience with hotkey + tray
- Could be integrated as the Phase 5+ voice layer

### Recommendation for Phase 2
**Do not build voice in Phase 2.** The value is lower than status/brief/research/work, and the hotkey/tray integration is finicky on Windows. Keep LiveKit/RoomKit as a Phase 5+ research item. In the meantime we can prototype a simple `ev listen` command that records audio and passes it to local Whisper if you want early voice experimentation.

## Sources
- [NVIDIA NIM API Tutorial](https://dreamprompting.com/blog/nvidia-nim-api-tutorial)
- [NVIDIA NIM Chat Completions Reference](https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-120b-infer)
- [NVIDIA NeMo Retriever Embedding API](https://docs.nvidia.com/nim/nemo-retriever/embedding/2.3/use-the-api-openai.html)
- [Build Your First AI Voice Agent in Python — LiveKit](https://livekit.com/blog/build-your-first-ai-voice-agent-python)
- [Local LiveKit Plugins](https://github.com/CoreWorxLab/local-livekit-plugins)
- [RoomKit UI — Desktop Voice Assistant](https://github.com/roomkit-live/roomkit-ui)
- [Tara — Local Voice Assistant with Orpheus TTS](https://github.com/dwain-barnes/tara-orpheus-livekit)
