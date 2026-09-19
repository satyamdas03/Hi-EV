"""Eval cases for semantic memory retrieval."""

import pytest

from ev.tools.memory_tool import MemoryTool

from .judge import EvalResult, async_timed, contains_score

MEMORY_CASES = [
    ("What did I decide about the motor controller?", ["foc", "stm32g4"], "robocad"),
    ("What did I note about the motor bracket?", ["stainless steel", "thermal conductivity"], "robocad"),
    ("What is the open issue on RoboCAD?", ["thermal simulation", "high-load joints"], "robocad"),
]


@pytest.mark.parametrize("query,expected,project_name", MEMORY_CASES)
async def test_memory_eval(eval_db, query, expected, project_name):
    store = eval_db
    tool = MemoryTool()
    tool.bind_store(store)
    response, latency_ms = await async_timed(tool.run(query=query, project_name=project_name))

    score = contains_score(response["text"], expected)
    result = EvalResult(
        query=query,
        response=response["text"],
        expected=expected,
        category="memory",
        score=score,
        latency_ms=latency_ms,
        metadata={"chunk_count": len(response.get("chunks", []))},
    )
    print(f"[{result.category}] score={result.score:.2f} latency={result.latency_ms}ms | {query}")
    assert score >= 0.5, f"Expected {expected} in response: {response['text']}"
