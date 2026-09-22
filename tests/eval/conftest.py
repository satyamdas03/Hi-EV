"""Shared fixtures for the Hi-EV eval harness."""

import hashlib
import os
import random
import tempfile
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore


def pytest_configure(config):
    """Use a file-based SQLite database for eval tests so the engine disposes cleanly."""
    db_path = Path(tempfile.gettempdir()) / f"hiev_eval_{os.getpid()}.db"
    os.environ["EV_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    with suppress(Exception):
        from ev.config import get_settings
        from ev.db.base import get_engine, get_session_maker

        get_engine.cache_clear()
        get_session_maker.cache_clear()
        get_settings.cache_clear()


def pytest_sessionfinish(session, exitstatus):
    """Dispose the engine and remove the temporary eval database."""
    with suppress(Exception):
        import asyncio

        asyncio.run(engine.dispose())
    db_path = Path(tempfile.gettempdir()) / f"hiev_eval_{os.getpid()}.db"
    with suppress(Exception):
        db_path.unlink(missing_ok=True)


class _FakeEmbeddingModel:
    """Deterministic, offline fake embedding model for fast eval tests."""

    dimension = 384

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(_FakeEmbeddingModel.dimension)]

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    def encode_one(self, text: str) -> list[float]:
        return self._vector_for(text)


@pytest.fixture
async def eval_db():
    """A seeded in-memory database with known golden facts."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        store = MemoryStore(session)

        # RoboCAD project with explicit phase and goal.
        await store.get_or_create_project(
            "RoboCAD",
            current_phase="Phase 29",
            repo_path="/repos/RoboCAD",
            goal="Build an AI-powered generative engineering platform for robotics.",
        )

        # Hi-EV project.
        await store.get_or_create_project(
            "Hi-EV",
            current_phase="Phase B",
            repo_path="/repos/Hi-EV",
            goal="Local-first personal AI operating system.",
        )

        # Known ingest records with ground-truth facts.
        await store.upsert_ingest([
            {
                "source": "github_commits",
                "source_id": "RoboCAD:sha1",
                "content_hash": "h1",
                "content": "feat: deliver Phase 29",
                "project_tag": "robocad",
                "privacy_level": "personal",
                "trusted": False,
            },
            {
                "source": "notes",
                "source_id": "robocad/decisions.md",
                "content_hash": "h2",
                "content": "Decided to use stainless steel for the motor bracket because of thermal conductivity.",
                "project_tag": "robocad",
                "privacy_level": "personal",
                "trusted": True,
            },
            {
                "source": "github_issues",
                "source_id": "RoboCAD:42",
                "content_hash": "h3",
                "content": "Issue: thermal simulation failing for high-load joints\nstate: open\n",
                "project_tag": "robocad",
                "privacy_level": "personal",
                "trusted": False,
            },
        ])

        # Explicit decision record.
        await store.upsert_decisions([
            {
                "topic": "Motor controller architecture",
                "decision_text": "Use FOC control with an STM32G4.",
                "rationale": "Better torque ripple at low speeds.",
                "source": "user_memory",
                "source_id": "decision-motor-ctrl",
                "project_name": "robocad",
            }
        ])

        # Calendar event for prep eval (kept within the default 24h window).
        event_start = datetime.now(UTC) + timedelta(hours=4)
        event_end = event_start + timedelta(hours=1)
        await store.upsert_ingest([
            {
                "source": "calendar_events",
                "source_id": "cal-review-1",
                "content_hash": "h4",
                "content": (
                    "Event: RoboCAD review\n"
                    "Description: quarterly review of RoboCAD progress\n"
                    f"Start: {event_start.isoformat()}\n"
                    f"End: {event_end.isoformat()}\n"
                    "Attendees: 2"
                ),
                "project_tag": "robocad",
                "privacy_level": "sensitive",
                "trusted": False,
            }
        ])
        await store.upsert_deadlines([
            {
                "title": "RoboCAD review",
                "due_date": datetime.now(UTC) + timedelta(hours=4),
                "source": "calendar",
                "source_id": "cal-review-1",
                "priority": "high",
                "project_name": "robocad",
            }
        ])

        # Index semantic chunks.
        from ev.memory.chunks import chunk_ingest_records
        records = [
            {
                "source": "notes",
                "source_id": "robocad/decisions.md",
                "content": "Decided to use stainless steel for the motor bracket because of thermal conductivity.",
                "project_tag": "robocad",
                "trusted": True,
            },
            {
                "source": "user_memory",
                "source_id": "decision-motor-ctrl",
                "content": "Motor controller architecture decision: Use FOC control with an STM32G4 for better torque ripple at low speeds.",
                "project_tag": "robocad",
                "trusted": True,
            },
            {
                "source": "github_issues",
                "source_id": "RoboCAD:42",
                "content": "Issue: thermal simulation failing for high-load joints\nstate: open\n",
                "project_tag": "robocad",
                "trusted": False,
            },
        ]
        await store.upsert_document_chunks(chunk_ingest_records(records))

    yield store

    await session.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _fake_embeddings_for_eval():
    """Use a deterministic fake embedding model so eval tests stay fast and offline."""
    fake = _FakeEmbeddingModel()
    with patch("ev.embeddings.get_embedding_model", return_value=fake):
        yield
