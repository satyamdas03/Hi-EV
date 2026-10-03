"""Data models for the Hi-EV eval runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCase:
    """A single eval case: run a tool with args and check expectations."""

    name: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Outcome of running one eval case."""

    case: EvalCase
    passed: bool
    actual: Any
    checks: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    error: str | None = None


@dataclass
class EvalSuite:
    """A named collection of eval cases loaded from one file."""

    name: str
    cases: list[EvalCase]


@dataclass
class EvalSuiteResult:
    """Aggregated result for a suite."""

    suite: EvalSuite
    results: list[EvalResult]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total(self) -> int:
        return len(self.results)
