import pytest
from click.testing import CliRunner
from ev.cli.main import cli
from ev.db.base import Base, engine, SessionLocal
from ev.memory.store import MemoryStore


@pytest.fixture
async def seeded_store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project("RoboCAD", current_phase="Phase 29")
        await store.upsert_ingest([{
            "source": "github_commits", "source_id": "RoboCAD:sha1", "content_hash": "h1",
            "content": "feat: deliver Phase 29", "project_tag": "robocad", "privacy_level": "personal"
        }])
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_status_command(seeded_store):
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "RoboCAD"])
    assert result.exit_code == 0
    assert "RoboCAD" in result.output
    assert "Phase 29" in result.output
