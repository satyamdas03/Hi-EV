"""Eval cases for web research (network-free with mocked search)."""

from unittest.mock import AsyncMock

import pytest

from ev.tools.research_tool import ResearchTool

from .judge import EvalResult, async_timed, contains_score

RESEARCH_CASES = [
    (
        "What is MuJoCo used for in robotics?",
        ["mujoco", "physics", "simulation"],
    ),
    (
        "Latest NVIDIA Jetson module",
        ["jetson", "nvidia", "module"],
    ),
]


@pytest.mark.parametrize("query,expected", RESEARCH_CASES)
async def test_research_eval(eval_db, query, expected):
    store = eval_db
    tool = ResearchTool()
    tool.bind_store(store)

    # Mock the search backend so evals are deterministic and offline-safe.
    tool.search.search = AsyncMock(
        return_value=[
            {
                "title": f"Result for {query}",
                "url": "https://example.com/result",
                "snippet": f"This page explains that {query} involves relevant concepts.",
            }
        ]
    )

    def _fake_llm(messages, **kwargs):
        prompt = messages[0]["content"] if messages else ""
        if "MuJoCo" in prompt:
            return "MuJoCo is a physics engine widely used in robotics for simulation, reinforcement learning, and control research. Source: [1]"
        if "Jetson" in prompt or "jetson" in prompt:
            return "The latest NVIDIA Jetson module brings a compact edge-AI platform with a GPU module and carrier board for robotics. Source: [1]"
        return "EV: I couldn't synthesize a specific answer for that query."

    tool.llm.complete = AsyncMock(side_effect=_fake_llm)
    # Disable Redis cache so evals don't wait on connection timeouts.
    tool._redis_client = lambda: None

    response, latency_ms = await async_timed(tool.run(query=query))
    answer = response.get("answer", "") if isinstance(response, dict) else str(response)

    score = contains_score(answer, expected)
    result = EvalResult(
        query=query,
        response=answer,
        expected=expected,
        category="research",
        score=score,
        latency_ms=latency_ms,
        metadata={"source_count": len(response.get("sources", [])) if isinstance(response, dict) else 0},
    )
    print(f"[{result.category}] score={result.score:.2f} latency={result.latency_ms}ms | {query}")
    assert score >= 0.5, f"Expected {expected} in answer: {answer}"
