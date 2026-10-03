"""Parser for Hi-EV SKILL.md manifests.

Supports YAML/TOML-style frontmatter and a free-form markdown body. The body
may contain `{parameter}` placeholders that are rendered at execution time.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from ev.skills.types import SkillManifest, SkillParameter

logger = logging.getLogger(__name__)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_skill_file(path: Path) -> SkillManifest | None:
    """Parse a SKILL.md file into a `SkillManifest`.

    Returns None if the file is missing required fields or is malformed.
    """
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        logger.warning("Skill file %s has no frontmatter; skipping", path)
        return None

    frontmatter_text, body = match.groups()
    try:
        meta = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        logger.warning("Invalid frontmatter in %s: %s", path, exc)
        return None

    if not isinstance(meta, dict):
        logger.warning("Skill frontmatter in %s is not a mapping", path)
        return None

    name = meta.get("name")
    if not name:
        logger.warning("Skill %s missing required 'name' field", path)
        return None

    parameters = _parse_parameters(meta.get("parameters", {}))
    return SkillManifest(
        name=str(name),
        description=meta.get("description", ""),
        version=str(meta.get("version", "0.1.0")),
        author=meta.get("author"),
        parameters=parameters,
        body=body.strip(),
        source_dir=path.parent,
        has_run_py=(path.parent / "run.py").exists(),
    )


def _parse_parameters(raw: Any) -> list[SkillParameter]:
    if isinstance(raw, list):
        return [_param_from_dict(p) for p in raw if isinstance(p, dict)]
    if isinstance(raw, dict):
        return [
            SkillParameter(
                name=key,
                type=value.get("type", "string") if isinstance(value, dict) else "string",
                description=(value.get("description", "") if isinstance(value, dict) else ""),
                required=value.get("required", True) if isinstance(value, dict) else True,
                default=(value.get("default") if isinstance(value, dict) else None),
            )
            for key, value in raw.items()
        ]
    return []


def _param_from_dict(raw: dict[str, Any]) -> SkillParameter:
    name = raw.get("name")
    if not name:
        name = "unnamed"
    return SkillParameter(
        name=str(name),
        type=str(raw.get("type", "string")),
        description=str(raw.get("description", "")),
        required=bool(raw.get("required", True)),
        default=raw.get("default"),
    )
