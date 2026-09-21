# Hi-EV — End-to-End Architecture & Vision Map

This document is a living map of the Hi-EV system as it exists today and the direction it is heading. Each diagram is rendered from Mermaid source so it can be edited and regenerated.

---

## 1. High-level system context

```mermaid
flowchart TB
    subgraph User["👤 User"]
        Voice["Voice / Speech"]
        Browser["Browser HUD\nlocalhost:5173"]
        CLI["ev CLI"]
    end

    subgraph Laptop["💻 Personal RTX 5060 Laptop"]
        direction TB
        Daemon["evd — FastAPI daemon\n127.0.0.1:7345"]
        WebFrontend["web/ — React + Three.js HUD"]
        LocalDB[("SQLite + sqlite-vec\n~/.hiev/hiev.db")]
    end

    subgraph Cloud["☁️ Optional Cloud Relay"]
        Relay["Webhook ingress\nQueue when laptop sleeps"]
        Telegram["Telegram bot\n(Phase C)"]
    end

    subgraph External["🌐 External APIs"]
        GitHubAPI["GitHub REST API"]
        GoogleAPI["Google Gmail + Calendar"]
        LLMAPI["NVIDIA / Anthropic / OpenAI"]
        WebSearch["DuckDuckGo web search"]
    end

    Voice --"SpeechRecognition"--> Browser
    Browser --"WebSocket /ws"--> Daemon
    CLI --"HTTP API"--> Daemon
    Daemon --"REST / streaming"--> LLMAPI
    Daemon --"REST"--> GitHubAPI
    Daemon --"OAuth2"--> GoogleAPI
    Daemon --"HTML"--> WebSearch
    Daemon --"SQLAlchemy"--> LocalDB
    Relay --"TLS/mTLS"--> Daemon
    Telegram --"Relay"--> Relay
```

---

## 2. Daemon component architecture

```mermaid
flowchart TB
    subgraph FastAPI["src/ev/server/api.py — FastAPI app"]
        CORS["CORS middleware\nlocalhost:5173"]
        Lifespan["Lifespan: scheduler, DB, state"]
        REST["REST routes\n/status /brief /research /prep ..."]
        WSRoute["/ws WebSocket route"]
    end

    subgraph Chat["src/ev/server/chat.py — per-connection"]
        ChatSession["ChatSession"]
        History["Rolling history\n(max 20 turns)"]
        GuardCheck{"Guard.check()"}
        Router["route_request()"]
        Intent["_classify_intent()"]
        Stream["_stream_chat()"]
        ToolRun["_run_tool()"]
    end

    subgraph Reasoning["src/ev/reasoning/router.py"]
        FastPath["fast — chat / simple lookup"]
        AgentPath["agent — tool chain / bounded summary"]
        DeliberatePath["deliberate — planning / uncertain"]
    end

    subgraph Safety["src/ev/security/"]
        Guard["guard.py\nSAFE / CAUTION / BLOCKED"]
        Boundary["boundary.py\npersonal_only + blocklist"]
    end

    subgraph Tools["src/ev/tools/"]
        Registry["registry.py\nToolRegistry + tiers"]
        StatusTool["StatusTool (T0)"]
        BriefTool["BriefTool (T0)"]
        MemoryTool["MemoryTool (T0)"]
        ResearchTool["ResearchTool (T0)"]
        PrepTool["PrepTool (T0)"]
        WorkTool["WorkTool (T1)"]
        DraftTools["DraftCommitTool / DraftPrTool / DraftReplyTool (T1)"]
    end

    subgraph Memory["src/ev/memory/"]
        Store["store.py\nMemoryStore"]
        Chunks["chunks.py\nsemantic chunker"]
        Vector["vector.py\nsqlite-vec helpers"]
    end

    subgraph LLM["src/ev/llm/client.py"]
        LLMClient["LLMClient"]
        Complete["complete()"]
        CompleteStream["complete_stream()"]
    end

    subgraph Ingestion["src/ev/ingestion/"]
        Scheduler["server/scheduler.py\ningest_loop"]
        Notes["notes.py"]
        GitHub["github.py"]
        Gmail["gmail.py"]
        Calendar["calendar.py"]
    end

    WSRoute --> ChatSession
    ChatSession --> GuardCheck
    ChatSession --> Router
    ChatSession --> Intent
    ChatSession --> Stream
    ChatSession --> ToolRun
    ChatSession --> History

    GuardCheck --> Guard
    Guard --> Boundary

    Router --> FastPath
    Router --> AgentPath
    Router --> DeliberatePath

    ToolRun --> Registry
    Registry --> StatusTool
    Registry --> BriefTool
    Registry --> MemoryTool
    Registry --> ResearchTool
    Registry --> PrepTool
    Registry --> WorkTool
    Registry --> DraftTools

    Tools --> Store
    Store --> Chunks
    Store --> Vector
    Store --> LocalDB

    Stream --> LLMClient
    Intent --> LLMClient
    ResearchTool --> LLMClient
    LLMClient --> Complete
    LLMClient --> CompleteStream

    Scheduler --> Notes
    Scheduler --> GitHub
    Scheduler --> Gmail
    Scheduler --> Calendar
    Ingestion --> Store
```

---

## 3. Request lifecycle: voice to answer

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Browser HUD
    participant SR as Web Speech API
    participant WS as /ws WebSocket
    participant CS as ChatSession
    participant G as Guard
    participant R as Reasoning Router
    participant IC as Intent Classifier
    participant LLM as LLMClient
    participant TR as ToolRegistry
    participant Mem as MemoryStore
    participant TTS as speechSynthesis

    U->>FE: press Space
    FE->>SR: startListening()
    Note over FE: phase = listening
    U->>SR: "status of RoboCAD"
    SR-->>FE: interim + final transcript
    FE->>FE: addUserTurn(text)
    FE->>WS: sendTranscript(text)
    WS->>CS: handle_message(type=transcript)

    CS->>G: check(text, source=user, trusted=True)
    alt BLOCKED
        G-->>CS: BLOCKED + reason
        CS-->>WS: phase=error, delta=reason, done
        WS-->>FE: render error
    else SAFE
        CS->>R: route_request(text, context)
        R-->>CS: route = fast | agent | deliberate
        CS-->>WS: phase=route:<fast|agent|deliberate>

        CS->>IC: classify intent with LLM
        IC-->>CS: {tool, args} or chat

        alt chat + fast path + streaming enabled
            CS-->>WS: phase=streaming
            CS->>LLM: complete_stream(messages)
            loop each delta
                LLM-->>CS: delta text
                CS-->>WS: delta text
                WS-->>FE: append to EV bubble + caret
            end
            CS-->>WS: done
            FE->>TTS: speak full response
        else tool intent
            CS->>TR: get(tool, guard_decision=...)
            TR->>Mem: query / upsert / search
            TR-->>CS: result text
            CS-->>WS: delta=result, done
            WS-->>FE: render result
            FE->>TTS: speak result
        end

        CS->>CS: append assistant turn to history
        FE->>FE: phase = dormant
    end
```

---

## 4. Ingestion pipeline

```mermaid
flowchart LR
    Sources["Sources"]
    Notes["📝 Notes vault\nnotes.py"]
    GitHub["🔧 GitHub repos\ngithub.py"]
    Gmail["📧 Gmail\ngmail.py"]
    Calendar["📅 Calendar\ncalendar.py"]

    Boundary{"personal_only\n+ blocklist"}
    Normalize["Normalize to\nIngest records"]
    TrustTag["Tag source trust\nnotes/user_memory = trusted\ngmail/calendar/github = untrusted"]
    Chunker["Chunker\nparagraph → sentence → word"]
    Embed["Embedding model\nall-MiniLM-L6-v2"]
    Structured[("Structured tables\nprojects, deadlines, people,\nobligations, decisions, events")]
    Vectors[("sqlite-vec\nDocumentChunk vectors")]
    Scheduler["Daemon scheduler loop\ningest_loop()"]

    Sources --> Notes & GitHub & Gmail & Calendar
    Notes & GitHub & Gmail & Calendar --> Boundary
    Boundary --> Normalize
    Normalize --> TrustTag
    TrustTag --> Chunker
    Chunker --> Embed
    Embed --> Vectors
    Normalize --> Structured
    Scheduler --> Notes & GitHub & Gmail & Calendar
```

---

## 5. Memory model

```mermaid
flowchart TB
    subgraph Structured["1. Structured facts"]
        Projects["projects"]
        Deadlines["deadlines"]
        People["people"]
        Obligations["obligations"]
        Decisions["decisions"]
    end

    subgraph Document["2. Document memory"]
        Ingest["ingest records"]
        Chunks["DocumentChunk rows"]
        Vec["sqlite-vec virtual table\nvec_document_chunks"]
        Hybrid["Hybrid search:\nKNN + keyword + recency + source"]
    end

    subgraph Episodic["3. Episodic log"]
        Events["events table\nevery turn, tool call, decision"]
    end

    subgraph Retrieval["Retrieval Router"]
        Intent["intent classification"]
        Route["route to relevant slices"]
        Rerank["rerank + cap context"]
    end

    UserQuery["User query"] --> Intent
    Intent --> Route
    Route --> Structured
    Route --> Document
    Route --> Episodic
    Structured --> Rerank
    Document --> Hybrid --> Rerank
    Episodic --> Rerank
    Rerank --> LLM["LLM / Tool answer"]
```

---

## 6. Safety, guard, and tier enforcement

```mermaid
flowchart TD
    Input["User input / untrusted content"]
    Guard["Guard.classify()\nsafe / caution / blocked"]
    Block["BLOCKED\nreturn refusal"]
    Tier0["T0 — Read / research\nauto-execute"]
    Tier1["T1 — Reversible write\nauto-execute + loud audit log"]
    Tier2["T2 — Consequential\nexplicit confirmation"]
    Tier3["T3 — Never automated\nhard block"]
    TrustDowngrade["Derived from untrusted text?\n↓ downgrade one tier"]
    ToolRun["Tool.run()"]
    Audit["events table\naudit log"]

    Input --> Guard
    Guard -->|blocked| Block
    Guard -->|safe/caution| TrustDowngrade
    TrustDowngrade --> Tier0
    TrustDowngrade --> Tier1
    TrustDowngrade --> Tier2
    TrustDowngrade --> Tier3
    Tier0 --> ToolRun
    Tier1 --> ToolRun
    Tier2 -->|await confirmation| ToolRun
    Tier3 -->|refuse| Block
    ToolRun --> Audit
```

---

## 7. Eval harness

```mermaid
flowchart LR
    Conftest["tests/eval/conftest.py\nseeded fixtures + fake embeddings"]
    Judge["tests/eval/judge.py\ncontains_score, refusal_score, async_timed"]
    EvalFiles["tests/eval/test_*_eval.py\nstatus, memory, research, prep, refusal"]
    Runner["scripts/run_eval.py\npytest parser + aggregator"]
    Report["eval_report.json\nper-category scores + latency"]

    Conftest --> EvalFiles
    Judge --> EvalFiles
    EvalFiles --> Runner
    Runner --> Report
```

---

## 8. Frontend streaming UI state machine

```mermaid
stateDiagram-v2
    [*] --> offline: page load
    offline --> boot: click INITIALISE / Space
    boot --> dormant: after 3s
    dormant --> listening: hold Space / click
    listening --> thinking: transcript sent
    thinking --> streaming: fast path + stream enabled
    thinking --> speaking: tool result / non-stream chat
    streaming --> speaking: done
    speaking --> dormant: TTS finished
    streaming --> dormant: STOP button / stop message
    dormant --> [*]: close tab
```

---

## 9. Roadmap to the full vision

```mermaid
gantt
    title Hi-EV Phased Roadmap
    dateFormat 2026-09-01
    section Completed
    Phase A :done, a, 2026-09-01, 2026-09-17
    Phase B :done, b, 2026-09-17, 2026-09-19
    section In Progress / Next
    Phase C :active, c, 2026-09-19, 2026-10-10
    section Planned
    Phase D :d, 2026-10-10, 2026-11-10
    Phase E :e, 2026-11-10, 2026-12-25
```

---

## 10. End-state vision architecture

```mermaid
flowchart TB
    subgraph EndUser["User — any device"]
        Voice2["Wake word / local STT (faster-whisper)"]
        HUD2["Holographic HUD / HTML blades"]
        Phone2["Telegram fallback"]
    end

    subgraph EndLaptop["Personal RTX 5060 — the brain"]
        Core["EV Core (asyncio + FastAPI)"]
        Memory2["Unified memory:\nstructured + vector + episodic"]
        Reasoning2["Reasoning router + planner"]
        Guard2["Guard + safety shell"]
        ToolSelf["Self-authoring tool loop"]
        LocalTTS["Kokoro / Piper TTS"]
        Vision["Local vision\nscreenshots, diagrams"]
    end

    subgraph MinimalCloud["Minimal cloud relay"]
        Webhooks["Webhook ingress"]
        Queue["Job queue"]
        TelegramRelay["Telegram relay"]
    end

    Voice2 --> Core
    HUD2 --> Core
    Phone2 --> MinimalCloud --> Core
    Core --> Memory2
    Core --> Reasoning2
    Core --> Guard2
    Core --> ToolSelf
    Core --> LocalTTS
    Core --> Vision
```

---

## Key file map

| Area | Primary files |
|------|---------------|
| Daemon / API | `src/ev/server/api.py`, `src/ev/server/chat.py`, `src/ev/server/scheduler.py` |
| Reasoning | `src/ev/reasoning/router.py` |
| Safety | `src/ev/security/guard.py`, `src/ev/security/boundary.py` |
| Tools | `src/ev/tools/registry.py`, `src/ev/tools/*_tool.py` |
| LLM | `src/ev/llm/client.py` |
| Memory | `src/ev/memory/store.py`, `src/ev/memory/chunks.py`, `src/ev/db/vector.py` |
| Ingestion | `src/ev/ingestion/notes.py`, `github.py`, `gmail.py`, `calendar.py` |
| Database | `src/ev/db/models.py`, `src/ev/db/base.py` |
| Frontend | `web/src/App.tsx`, `store.ts`, `lib/bridge.ts`, `lib/voice.ts`, `ui/Chat.tsx`, `scene/Scene.tsx` |
| Eval | `tests/eval/`, `scripts/run_eval.py` |
| Config | `src/ev/config.py`, `.env` |
