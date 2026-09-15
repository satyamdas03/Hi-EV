"""Hi-EV internal FastAPI daemon."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from ev.config import get_settings
from ev.db.base import SessionLocal
from ev.memory.store import MemoryStore
from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    yield {}


app = FastAPI(title="EV Daemon API", lifespan=lifespan)


class StatusRequest(BaseModel):
    project: str


@app.post("/status")
async def status_endpoint(req: StatusRequest):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        registry = ToolRegistry(store)
        registry.register(StatusTool())
        summary = await registry.get("status").run(project=req.project)
        return {"summary": summary}


@app.get("/health")
async def health():
    return {"status": "ok"}
