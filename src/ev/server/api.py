"""Hi-EV internal FastAPI daemon."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from ev.config import get_settings
from ev.db.base import SessionLocal
from ev.memory.store import MemoryStore
from ev.tools.brief_tool import BriefTool
from ev.tools.draft_tools import DraftCommitTool, DraftPrTool, DraftReplyTool
from ev.tools.registry import ToolRegistry
from ev.tools.research_tool import ResearchTool
from ev.tools.status_tool import StatusTool
from ev.tools.work_tool import WorkTool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    yield {}


app = FastAPI(title="EV Daemon API", lifespan=lifespan)


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


@app.get("/health")
async def health():
    return {"status": "ok"}
