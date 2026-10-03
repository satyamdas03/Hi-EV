"""Load eval suites from JSON/YAML files on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from ev.eval.models import EvalCase, EvalSuite


def _build_case(data: dict[str, Any]) -> EvalCase:
    return EvalCase(
        name=data["name"],
        tool=data["tool"],
        args=data.get("args", {}),
        expect=data.get("expect", {}),
    )


def load_suite(path: Path) -> EvalSuite:
    """Load a single suite file (.json, .yaml, or .yml)."""
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        if not HAS_YAML:
            raise ImportError("PyYAML is required to load YAML eval suites")
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported eval suite format: {suffix}")

    cases = [_build_case(c) for c in data.get("cases", [])]
    return EvalSuite(name=data.get("suite", path.stem), cases=cases)


def load_suites(directory: Path) -> list[EvalSuite]:
    """Load every suite file in a directory."""
    if not directory.exists():
        return []
    suites: list[EvalSuite] = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in (".json", ".yaml", ".yml"):
            suites.append(load_suite(path))
    return suites
