"""Console and JSON reporting for eval results."""

from __future__ import annotations

import json
from typing import Any

from ev.eval.models import EvalSuiteResult


def text_report(results: list[EvalSuiteResult]) -> str:
    """Return a human-readable eval report."""
    lines: list[str] = []
    total_passed = 0
    total_cases = 0
    for suite_result in results:
        lines.append(f"\nSuite: {suite_result.suite.name}")
        for r in suite_result.results:
            total_cases += 1
            if r.passed:
                total_passed += 1
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"  [{status}] {r.case.name} ({r.latency_ms}ms)"
                + (f" — error: {r.error}" if r.error else "")
            )
            for check in r.checks:
                if not check.get("passed"):
                    lines.append(f"      check failed: {check}")
    lines.append(f"\nTotal: {total_passed}/{total_cases} passed")
    return "\n".join(lines)


def json_report(results: list[EvalSuiteResult]) -> str:
    """Return a JSON eval report."""
    payload: list[dict[str, Any]] = []
    for suite_result in results:
        payload.append(
            {
                "suite": suite_result.suite.name,
                "passed": suite_result.passed,
                "total": suite_result.total,
                "cases": [
                    {
                        "name": r.case.name,
                        "passed": r.passed,
                        "latency_ms": r.latency_ms,
                        "error": r.error,
                        "checks": r.checks,
                        "actual": r.actual,
                    }
                    for r in suite_result.results
                ],
            }
        )
    return json.dumps(payload, indent=2, default=str)
