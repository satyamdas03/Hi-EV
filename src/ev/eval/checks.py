"""Assertion helpers for eval cases."""

from __future__ import annotations

import json
import re
from typing import Any


def run_checks(actual: Any, expect: dict[str, Any]) -> dict[str, Any]:
    """Run all checks in `expect` against `actual` and return a summary."""
    if not expect:
        return {"passed": True, "checks": []}

    results: list[dict[str, Any]] = []
    for key, value in expect.items():
        if key == "contains":
            results.append(_contains(actual, value))
        elif key == "exact":
            results.append(_exact(actual, value))
        elif key == "regex":
            results.append(_regex(actual, value))
        elif key == "json_path":
            results.append(_json_path(actual, value))
        else:
            results.append({"name": key, "passed": False, "message": f"Unknown check '{key}'"})

    return {"passed": all(r["passed"] for r in results), "checks": results}


def _contains(actual: Any, expected: str | list[str]) -> dict[str, Any]:
    text = str(actual).lower()
    tokens = [expected] if isinstance(expected, str) else expected
    missing = [str(t) for t in tokens if str(t).lower() not in text]
    return {"name": "contains", "passed": not missing, "missing": missing}


def _exact(actual: Any, expected: Any) -> dict[str, Any]:
    return {
        "name": "exact",
        "passed": str(actual).strip() == str(expected).strip(),
    }


def _regex(actual: Any, pattern: str) -> dict[str, Any]:
    return {"name": "regex", "passed": bool(re.search(pattern, str(actual)))}


def _json_path(actual: Any, spec: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(actual) if isinstance(actual, str) else actual
    except Exception as exc:  # noqa: BLE001
        return {"name": "json_path", "passed": False, "error": str(exc)}

    keys = str(spec.get("path", "")).strip("$").strip(".").split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            value = None
            break

    expected = spec.get("equals")
    return {"name": "json_path", "passed": value == expected, "actual": value}
