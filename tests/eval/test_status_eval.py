"""Eval cases for project-status queries."""

import pytest

from ev.tools.registry import ToolRegistry
from ev.tools.status_tool import StatusTool

from .judge import EvalResult, async_timed, contains_score

STATUS_CASES = [
    ("What phase is RoboCAD in?", ["phase 29"]),
    ("Status of RoboCAD", ["robocad", "phase 29"]),
    ("What is Hi-EV's current phase?", ["phase b"]),
]


@pytest.mark.parametrize("query,expected", STATUS_CASES)
async def test_status_eval(eval_db, query, expected):
    store = eval_db
    registry = ToolRegistry(store)
    registry.register(StatusTool())

    project_name = "RoboCAD" if "robocad" in query.lower() else "Hi-EV"
    response, latency_ms = await async_timed(
        registry.get("status").run(project=project_name)
    )

    score = contains_score(response, expected)
    result = EvalResult(
        query=query,
        response=response,
        expected=expected,
        category="status",
        score=score,
        latency_ms=latency_ms,
        metadata={},
    )
    print(f"[{result.category}] score={result.score:.2f} latency={result.latency_ms}ms | {query}")
    assert score >= 0.5, f"Expected {expected} in response: {response}"
