"""Eval runner that executes tool cases and produces a pass/fail report."""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from ev.eval.checks import run_checks
from ev.eval.loader import load_suites
from ev.eval.models import EvalCase, EvalResult, EvalSuite, EvalSuiteResult
from ev.skills.loader import load_skills_into_registry
from ev.tools.registry import ToolRegistry


class EvalRunner:
    """Discover and run eval suites against the live Hi-EV tool registry."""

    def __init__(self, suite_dirs: list[str | Path] | None = None, store: Any | None = None):
        self.suite_dirs = [Path(d) for d in (suite_dirs or [Path("evals")])]
        self.store = store
        # Ensure skills are visible to every per-case ToolRegistry.
        load_skills_into_registry()

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
            suite_setup_error: str | None = None
            if suite.setup_actions:
                ok, suite_setup_error = await self._run_setup_actions(suite.setup_actions)
                if not ok:
                    suite_setup_error = suite_setup_error or "suite setup failed"
            for case in suite.cases:
                if suite_setup_error:
                    suite_results.append(
                        EvalResult(
                            case=case,
                            passed=False,
                            actual=None,
                            checks=[],
                            latency_ms=0,
                            error=suite_setup_error,
                        )
                    )
                else:
                    suite_results.append(await self.run_case(case))
            results.append(EvalSuiteResult(suite=suite, results=suite_results))
        return results

    async def run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case and evaluate its expectations."""
        start = time.perf_counter()
        if case.setup_actions:
            ok, error = await self._run_setup_actions(case.setup_actions)
            if not ok:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                return EvalResult(
                    case=case,
                    passed=False,
                    actual=None,
                    checks=[],
                    latency_ms=elapsed_ms,
                    error=error or "case setup failed",
                )
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

    async def _run_setup_actions(self, actions: list[dict[str, Any]]) -> tuple[bool, str | None]:
        """Execute setup actions. Returns (ok, error_message)."""
        for action in actions:
            action_name = action.get("action")
            if action_name == "seed_notes":
                ok, error = await self._seed_notes(action)
                if not ok:
                    return False, error
            else:
                return False, f"Unknown setup action: {action_name!r}"
        return True, None

    async def _seed_notes(self, action: dict[str, Any]) -> tuple[bool, str | None]:
        """Seed notes into the memory store for a project."""
        if self.store is None:
            return False, "seed_notes requires a store but EvalRunner.store is None"
        project_name = action.get("project", "RoboCAD")
        project_tag = action.get("project_tag", project_name.lower())
        notes = action.get("notes", [])
        if not notes:
            return False, "seed_notes requires a non-empty 'notes' list"
        try:
            await self.store.get_or_create_project(project_name)
            records: list[dict[str, Any]] = []
            for note in notes:
                content = note.get("content", "")
                if not content:
                    return False, "every note in seed_notes must have 'content'"
                source_id = note.get("source_id", f"eval:{uuid.uuid4()}")
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                records.append(
                    {
                        "source": "notes",
                        "source_id": source_id,
                        "content_hash": content_hash,
                        "content": content,
                        "project_tag": project_tag,
                        "privacy_level": note.get("privacy_level", "personal"),
                    }
                )
            await self.store.upsert_ingest(records)
        except Exception as exc:  # noqa: BLE001
            return False, f"seed_notes failed: {exc}"
        return True, None
