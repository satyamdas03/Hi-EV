"""Hi-EV internal FastAPI daemon."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ev.config import get_settings
from ev.db.base import SessionLocal
from ev.memory.store import MemoryStore
from ev.server.chat import ChatSession
from ev.tools.alerts_tool import AlertsTool
from ev.tools.brief_tool import BriefTool
from ev.tools.calendar_prep_tool import CalendarPrepTool
from ev.tools.draft_tools import DraftCommitTool, DraftPrTool, DraftReplyTool
from ev.tools.memory_tool import MemoryTool, RememberTool
from ev.tools.obligations_tool import ObligationsTool
from ev.tools.people_tool import PeopleTool
from ev.tools.prep_tool import PrepTool
from ev.tools.registry import ToolRegistry
from ev.tools.research_tool import ResearchTool
from ev.tools.status_tool import StatusTool
from ev.tools.work_tool import WorkTool

logger = logging.getLogger(__name__)

# Origins allowed to talk to the local daemon from the browser client.
_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.active_websockets: set[WebSocket] = set()
    alert_task = asyncio.create_task(_alert_loop(settings))
    try:
        yield {}
    finally:
        alert_task.cancel()
        try:
            await alert_task
        except asyncio.CancelledError:
            pass
        for ws in list(getattr(app.state, "active_websockets", set())):
            with suppress(Exception):
                await ws.close()


async def _alert_loop(settings):
    """Background loop that emits urgent deadline digests."""
    from ev.tools.deadline_watcher import DeadlineWatcherTool

    while True:
        try:
            await asyncio.sleep(settings.alert_interval_sec)
        except asyncio.CancelledError:
            break
        if settings.kill_switch:
            continue
        if _in_quiet_hours(settings.quiet_start, settings.quiet_end):
            continue

        async with SessionLocal() as session:
            store = MemoryStore(session)
            watcher = DeadlineWatcherTool(urgent_hours=settings.alert_window_hours)
            watcher.bind_store(store)
            result = await watcher.run()
            urgent = result["urgent"]
            if not urgent:
                continue
            print(f"[EV ALERT] {result['counts']['urgent']} urgent deadline(s). Overdue: {result['counts']['overdue']}")
            for item in urgent:
                try:
                    from uuid import UUID
                    await store.mark_deadline_reminded(UUID(item["id"]))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to mark deadline reminded: %s", exc)


def _in_quiet_hours(start: str, end: str) -> bool:
    now = datetime.now(UTC).time()
    start_t = datetime.strptime(start, "%H:%M").time()  # noqa: DTZ007
    end_t = datetime.strptime(end, "%H:%M").time()  # noqa: DTZ007
    if start_t < end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t


app = FastAPI(title="EV Daemon API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StatusRequest(BaseModel):
    project: str


class ResearchRequest(BaseModel):
    query: str


class WorkRequest(BaseModel):
    project: str
    task: str


class DraftRequest(BaseModel):
    type: str  # commit, pr, reply
    project: str | None = None
    to: str | None = None
    subject: str | None = None
    snippet: str | None = None


class CalendarPrepRequest(BaseModel):
    time: str


class PrepRequest(BaseModel):
    title: str | None = None
    project: str | None = None
    time: str | None = None


class MemorySearchRequest(BaseModel):
    query: str
    project: str | None = None
    k: int = 5


class RememberRequest(BaseModel):
    text: str
    project: str | None = None


class ListFilterRequest(BaseModel):
    project: str | None = None
    status: str | None = None
    overdue: bool = False
    limit: int = 50


@app.post("/status")
async def status_endpoint(req: StatusRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(StatusTool())
        summary = await registry.get("status").run(project=req.project)
        return {"summary": summary}


@app.post("/brief")
async def brief_endpoint():
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(BriefTool())
        brief_text = await registry.get("brief").run()
        return {"brief": brief_text}


@app.post("/research")
async def research_endpoint(req: ResearchRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(ResearchTool())
        result = await registry.get("research").run(query=req.query)
        return result


@app.post("/work")
async def work_endpoint(req: WorkRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(WorkTool())
        result = await registry.get("work_on").run(project=req.project, task=req.task)
        return result


@app.post("/draft")
async def draft_endpoint(req: DraftRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        if req.type == "reply":
            registry = ToolRegistry(None)
            registry.register(DraftReplyTool())
            result = await registry.get("draft_reply").run(
                to=req.to or "",
                subject=req.subject or "",
                thread_snippet=req.snippet or "",
            )
            return result
        registry = ToolRegistry(store)
        if req.type == "commit":
            registry.register(DraftCommitTool())
            result = await registry.get("draft_commit").run(project=req.project or "")
        elif req.type == "pr":
            registry.register(DraftPrTool())
            result = await registry.get("draft_pr").run(project=req.project or "")
        else:
            return {"error": f"Unknown draft type: {req.type}"}
        return result


@app.post("/calendar-prep")
async def calendar_prep_endpoint(req: CalendarPrepRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(CalendarPrepTool())
        result = await registry.get("calendar_prep").run(time=req.time)
        return result


@app.post("/deadlines")
async def deadlines_endpoint(req: ListFilterRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        from ev.tools.deadline_watcher import DeadlineWatcherTool

        registry.register(DeadlineWatcherTool())
        result = await registry.get("deadline_watcher").run(project_name=req.project)
        return result


@app.post("/people")
async def people_endpoint(req: ListFilterRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(PeopleTool())
        result = await registry.get("people").run(project_name=req.project, limit=req.limit)
        return result


@app.post("/obligations")
async def obligations_endpoint(req: ListFilterRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(ObligationsTool())
        result = await registry.get("obligations").run(
            project_name=req.project,
            status=req.status,
            overdue=req.overdue,
        )
        return result


@app.post("/alerts")
async def alerts_endpoint(req: ListFilterRequest | None = None):
    project = req.project if req else None
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(AlertsTool())
        result = await registry.get("alerts").run(project_name=project)
        return result


@app.post("/prep")
async def prep_endpoint(req: PrepRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(PrepTool())
        result = await registry.get("prep").run(
            title=req.title,
            project_name=req.project,
            time=req.time,
        )
        return result


@app.post("/memory")
async def memory_endpoint(req: MemorySearchRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(MemoryTool())
        result = await registry.get("memory").run(
            query=req.query,
            project_name=req.project,
            k=req.k,
        )
        return result


@app.post("/remember")
async def remember_endpoint(req: RememberRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        tool = RememberTool()
        tool.bind_store(store)
        result = await tool.run(text=req.text, project_name=req.project)
        return result


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bi-directional conversation socket for the Hi-EV web client.

    Accepts transcript messages from the browser and streams back response deltas.
    Each connection gets its own ChatSession so conversation history is isolated.
    """
    await websocket.accept()
    app.state.active_websockets.add(websocket)
    session = ChatSession(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await session.handle_message(data)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket error: %s", exc)
    finally:
        app.state.active_websockets.discard(websocket)
        with suppress(Exception):
            await websocket.close()
