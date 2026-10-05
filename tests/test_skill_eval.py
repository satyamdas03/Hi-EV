"""Deterministic golden-dataset evals for built-in skills."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.eval.loader import load_suite
from ev.eval.runner import EvalRunner
from ev.memory.store import MemoryStore


@pytest.fixture
async def skill_eval_store():
    """Provide a fresh MemoryStore for skill evals with empty tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        store = MemoryStore(session)
        yield store
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


SKILLS_DIR = Path(__file__).resolve().parents[1] / "evals" / "skills"


@pytest.mark.asyncio
@patch("ev.skills.tool_adapter.LLMClient")
async def test_hello_ev_skill_suite(mock_llm_client, skill_eval_store):
    """The hello_ev skill greets by name and uses the default name."""
    llm = mock_llm_client.return_value
    llm.complete = AsyncMock(return_value="Hi Satyam, EV here — the local time is 09:42.")

    suite = load_suite(SKILLS_DIR / "hello_ev.json")
    runner = EvalRunner(suite_dirs=[SKILLS_DIR], store=skill_eval_store)
    results = await runner.run([suite])

    assert len(results) == 1
    suite_result = results[0]
    assert suite_result.passed == suite_result.total, json.dumps(
        _report(suite_result), indent=2, default=str
    )
    for result in suite_result.results:
        assert result.error is None
        assert result.actual["skill"] == "hello_ev"


@pytest.mark.asyncio
@patch("ev.skills.tool_adapter.LLMClient")
async def test_summarize_notes_skill_suite(mock_llm_client, skill_eval_store):
    """The summarize_notes skill runs against seeded RoboCAD notes."""
    llm = mock_llm_client.return_value
    llm.complete = AsyncMock(
        return_value="- RoboCAD completed Phase 22 with all tests passing.\n- Phase 23 will focus on humanoid robot synthesis."
    )

    suite = load_suite(SKILLS_DIR / "summarize_notes.json")
    runner = EvalRunner(suite_dirs=[SKILLS_DIR], store=skill_eval_store)
    results = await runner.run([suite])

    assert len(results) == 1
    suite_result = results[0]
    assert suite_result.total == 1
    assert suite_result.passed == 1, json.dumps(_report(suite_result), indent=2, default=str)

    result = suite_result.results[0]
    assert result.error is None
    assert result.actual["skill"] == "summarize_notes"
    # Verify seeding actually landed in the store.
    seeded = await skill_eval_store.recent_notes("RoboCAD", limit=5)
    assert len(seeded) == 2


@pytest.mark.asyncio
async def test_seed_notes_requires_store(tmp_path):
    """A seed_notes action without a store produces a clear setup error."""
    suite_path = tmp_path / "bad.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "bad_seed",
                "setup_actions": [
                    {
                        "action": "seed_notes",
                        "project": "RoboCAD",
                        "notes": [{"content": "note"}],
                    }
                ],
                "cases": [{"name": "x", "tool": "hello_ev", "args": {}, "expect": {}}],
            }
        )
    )
    runner = EvalRunner(suite_dirs=[tmp_path])
    results = await runner.run([load_suite(suite_path)])

    assert results[0].results[0].passed is False
    assert "store" in results[0].results[0].error.lower()


def _report(suite_result):
    return {
        "suite": suite_result.suite.name,
        "passed": suite_result.passed,
        "total": suite_result.total,
        "cases": [
            {
                "name": r.case.name,
                "passed": r.passed,
                "error": r.error,
                "actual": r.actual,
                "checks": r.checks,
            }
            for r in suite_result.results
        ],
    }
