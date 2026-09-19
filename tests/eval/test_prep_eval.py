"""Eval cases for pre-meeting / pre-deadline prep."""

from unittest.mock import AsyncMock

import pytest

from ev.tools.prep_tool import PrepTool

from .judge import EvalResult, async_timed, contains_score

PREP_CASES = [
    (
        "Prep me for the RoboCAD review",
        {"title": "RoboCAD review", "project_name": "robocad"},
        ["agenda", "talking points", "questions"],
    ),
]


@pytest.mark.parametrize("query,args,expected", PREP_CASES)
async def test_prep_eval(eval_db, query, args, expected):
    store = eval_db
    tool = PrepTool()
    tool.bind_store(store)
    tool._llm.complete = AsyncMock(
        return_value=(
            "Agenda:\n"
            "1. Review Phase 29 progress\n"
            "2. Discuss thermal simulation blockers\n\n"
            "Talking points:\n"
            "- Motor bracket material trade-off\n\n"
            "Open questions:\n"
            "- Timeline for STM32G4 bring-up?"
        )
    )

    response, latency_ms = await async_timed(
        tool.run(title=args.get("title"), project_name=args.get("project_name"))
    )

    prep_text = response.get("prep", "")
    score = contains_score(prep_text, expected)
    result = EvalResult(
        query=query,
        response=prep_text,
        expected=expected,
        category="prep",
        score=score,
        latency_ms=latency_ms,
        metadata={"event_found": response.get("event") is not None},
    )
    print(f"[{result.category}] score={result.score:.2f} latency={result.latency_ms}ms | {query}")
    assert score >= 0.5, f"Expected {expected} in prep: {prep_text}"
