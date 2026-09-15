import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.status import build_status_summary
from ev.memory.store import MemoryStore


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_status_summary_basic(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29", repo_url="https://github.com/satyamdas03/RoboCAD")
    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1", "content": "feat: Phase 29 delivered", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_issues", "source_id": "RoboCAD:42", "content_hash": "h2", "content": "bug: mesh fails\nstate: open\n\ndetails", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    summary = await build_status_summary(store, "RoboCAD")
    assert summary["name"] == "RoboCAD"
    assert summary["phase"] == "Phase 29"
    assert any("Phase 29 delivered" in c["content"] for c in summary["latest_commits"])
    assert len(summary["open_issues"]) == 1
    assert summary["open_issue_count"] == 1


async def test_status_summary_infers_phase_when_unset(store):
    await store.get_or_create_project("RoboCAD", current_phase=None)
    await store.upsert_ingest([
        {"source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1", "content": "feat: Phase 22 complete", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    summary = await build_status_summary(store, "RoboCAD")
    assert summary["phase"] == "Phase 22"
    assert "Phase 22" in summary["summary_text"]


async def test_status_summary_includes_counts(store):
    await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
    await store.upsert_ingest([
        {"source": "github_issues", "source_id": "RoboCAD:1", "content_hash": "h1", "content": "bug: a\nstate: open\n\nbody", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_issues", "source_id": "RoboCAD:2", "content_hash": "h2", "content": "bug: b\nstate: open\n\nbody", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "github_prs", "source_id": "RoboCAD:10", "content_hash": "h3", "content": "feat: x\nstate: open\n\nbody", "project_tag": "robocad", "privacy_level": "personal"},
        {"source": "notes", "source_id": "n1", "content_hash": "h4", "content": "design note", "project_tag": "robocad", "privacy_level": "personal"},
    ])
    summary = await build_status_summary(store, "RoboCAD")
    assert summary["open_issue_count"] == 2
    assert summary["open_pr_count"] == 1
    assert summary["recent_note_count"] == 1
    assert "2 open issue" in summary["summary_text"]
    assert "1 open PR" in summary["summary_text"]
    assert "1 recent note" in summary["summary_text"]
