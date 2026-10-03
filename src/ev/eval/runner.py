"""Eval runner that executes tool cases and produces a pass/fail report."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ev.eval.checks import run_checks
from ev.eval.loader import load_suites
from ev.eval.models import EvalCase, EvalResult, EvalSuite, EvalSuiteResult
from ev.tools.registry import ToolRegistry


class EvalRunner:
    """Discover and run eval suites against the live Hi-EV tool registry."""

    def __init__(self, suite_dirs: list[str | Path] | None = None, store: Any | None = None):
        self.suite_dirs = [Path(d) for d in (suite_dirs or [Path("evals")])]
        self.store = store

    def load(self) -> list[EvalSuite]:
        """Load all suites from the configured directories."""
        suites: list[EvalSuite] = []
        for directory in self.suite_dirs:
            suites.extend(load_suites(directory))
        return suites

    async def run(self, suites: list[EvalSuite] | None = None) -> list[EvalSuiteResult]:
        """Run every case in every suite and return aggregated results."""
        suites = suites if suites is not None else self.load()
        results: list[EvalSuiteResult] = []
        for suite in suites:
            suite_results: list[EvalResult] = []
            for case in suite.cases:
                suite_results.append(await self.run_case(case))
            results.append(EvalSuiteResult(suite=suite, results=suite_results))
        return results

    async def run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case and evaluate its expectations."""
        start = time.perf_counter()
        registry = ToolRegistry(self.store)
        try:
            tool = registry.get(case.tool)
            actual = await tool.run(**case.args)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            summary = run_checks(actual, case.expect)
            return EvalResult(
                case=case,
                passed=summary["passed"],
                actual=actual,
                checks=summary["checks"],
                latency_ms=elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return EvalResult(
                case=case,
                passed=False,
                actual=None,
                checks=[],
                latency_ms=elapsed_ms,
                error=str(exc),
            )
