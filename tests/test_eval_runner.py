"""Tests for the Hi-EV eval runner abstraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ev.eval.checks import run_checks
from ev.eval.loader import load_suite, load_suites
from ev.eval.models import EvalCase, EvalSuite
from ev.eval.runner import EvalRunner


def test_contains_check_passes():
    summary = run_checks("Hello world", {"contains": "world"})
    assert summary["passed"] is True


def test_contains_check_fails():
    summary = run_checks("Hello world", {"contains": "mars"})
    assert summary["passed"] is False


def test_exact_check_passes():
    summary = run_checks("42", {"exact": "42"})
    assert summary["passed"] is True


def test_json_path_check_passes():
    summary = run_checks('{"answer": 42}', {"json_path": {"path": "$.answer", "equals": 42}})
    assert summary["passed"] is True


def test_load_suite_from_json(tmp_path):
    suite_path = tmp_path / "math.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "math",
                "cases": [
                    {"name": "add", "tool": "sandbox", "args": {"code": "result = 1 + 1"}, "expect": {"exact": "2"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    suite = load_suite(suite_path)
    assert suite.name == "math"
    assert len(suite.cases) == 1
    assert suite.cases[0].tool == "sandbox"


def test_load_suites_ignores_non_suite_files(tmp_path):
    (tmp_path / "README.md").write_text("docs")
    suite_path = tmp_path / "math.json"
    suite_path.write_text(
        json.dumps({"suite": "math", "cases": []}),
        encoding="utf-8",
    )
    suites = load_suites(tmp_path)
    assert len(suites) == 1
    assert suites[0].name == "math"


@pytest.mark.anyio
async def test_runner_executes_sandbox_case(tmp_path):
    suite_path = tmp_path / "math.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "math",
                "cases": [
                    {
                        "name": "factorial",
                        "tool": "sandbox",
                        "args": {"code": "import math\nresult = math.factorial(5)"},
                        "expect": {"json_path": {"path": "$.result", "equals": 120}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = EvalRunner(suite_dirs=[tmp_path])
    results = await runner.run()
    assert len(results) == 1
    suite_result = results[0]
    assert suite_result.total == 1
    assert suite_result.passed == 1


@pytest.mark.anyio
async def test_runner_reports_failed_check():
    suite = EvalSuite(
        name="fail",
        cases=[EvalCase(name="bad", tool="sandbox", args={"code": "result = 1"}, expect={"exact": "2"})],
    )
    runner = EvalRunner(suite_dirs=[])
    results = await runner.run([suite])
    assert results[0].passed == 0
    assert results[0].results[0].passed is False
