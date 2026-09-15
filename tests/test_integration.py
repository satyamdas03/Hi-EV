"""End-to-end integration tests.

These are skipped unless EV_RUN_INTEGRATION=1 is set, because they hit live
GitHub and require a real .env with EV_GITHUB_TOKEN and EV_DATABASE_URL.
"""

import asyncio
import os

import pytest
from click.testing import CliRunner

from ev.cli.main import cli
from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore

pytestmark = pytest.mark.skipif(
    os.environ.get("EV_RUN_INTEGRATION") != "1",
    reason="Set EV_RUN_INTEGRATION=1 to run live integration tests",
)


async def _seed():
    """Ensure schema exists and RoboCAD has a project row for the CLI to query."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.get_or_create_project(
            "RoboCAD",
            repo_url="https://github.com/satyamdas03/RoboCAD",
        )


def test_integration_status():
    asyncio.run(_seed())
    runner = CliRunner(env={"EV_RUN_INTEGRATION": "1"})
    result = runner.invoke(cli, ["status", "RoboCAD"])
    assert result.exit_code == 0, result.output
    assert "RoboCAD" in result.output
