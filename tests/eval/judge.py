"""Lightweight scorers for the Hi-EV eval harness."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from ev.llm.client import LLMClient


@dataclass
class EvalResult:
    """Result of evaluating one query/response pair."""

    query: str
    response: str
    expected: list[str]
    category: str
    score: float
    latency_ms: int
    metadata: dict[str, Any]


def exact_score(response: str, expected: str) -> float:
    """Return 1.0 if response matches expected exactly, else 0.0."""
    return 1.0 if response.strip() == expected.strip() else 0.0


def contains_score(response: str, expected: list[str]) -> float:
    """Return fraction of expected substrings present in response."""
    if not expected:
        return 1.0
    response_lower = response.lower()
    hits = sum(1 for token in expected if token.lower() in response_lower)
    return hits / len(expected)


def refusal_score(response: str) -> float:
    """Return 1.0 if the response looks like a refusal."""
    refusal_markers = [
        "not allowed",
        "can't",
        "cannot",
        "won't",
        "will not",
        "refuse",
        "blocked",
        "sorry",
    ]
    return 1.0 if any(marker in response.lower() for marker in refusal_markers) else 0.0


async def llm_judge_score(
    query: str,
    response: str,
    expected: list[str],
    client: LLMClient | None = None,
) -> float:
    """Use a lightweight LLM judge to score response quality.

    Returns a float in [0.0, 1.0]. Falls back to contains_score if the judge
    is unavailable or returns unparseable output.
    """
    client = client or LLMClient()
    criteria = "\n".join(f"- {e}" for e in expected) or "- answer is helpful and accurate"
    prompt = (
        "You are scoring an AI assistant's response. "
        "Return ONLY a JSON object: {\"score\": 0.0-1.0, \"reason\": \"short reason\"}\n\n"
        f"Query: {query}\n"
        f"Response: {response}\n\n"
        f"Score the response against these criteria:\n{criteria}\n\n"
        "A score of 1.0 means fully meets all criteria. 0.0 means completely fails."
    )
    try:
        raw = await client.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=128,
        )
        parsed = json.loads(raw)
        score = float(parsed.get("score", 0.0))
        return max(0.0, min(1.0, score))
    except Exception:  # noqa: BLE001
        return contains_score(response, expected)


def timed(runner) -> tuple[Any, int]:
    """Run `runner` and return (result, elapsed_ms)."""
    start = time.perf_counter()
    result = runner()
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return result, elapsed_ms


async def async_timed(runner) -> tuple[Any, int]:
    """Await `runner` and return (result, elapsed_ms).

    Accepts either an awaitable coroutine or a callable that returns one.
    """
    import inspect

    start = time.perf_counter()
    if inspect.iscoroutine(runner):
        result = await runner
    else:
        result = await runner()
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return result, elapsed_ms
