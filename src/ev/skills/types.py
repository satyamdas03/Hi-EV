"""Skill manifest datatypes for Hi-EV.

A skill is a directory containing at minimum a `SKILL.md` file. The frontmatter
carries metadata (name, description, version, parameters); the body is a
human-readable and model-readable prompt template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillParameter:
    """One declared parameter for a skill."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any | None = None


@dataclass
class SkillManifest:
    """Parsed representation of a SKILL.md manifest."""

    name: str
    description: str = ""
    version: str = "0.1.0"
    author: str | None = None
    parameters: list[SkillParameter] = field(default_factory=list)
    body: str = ""
    source_dir: Path | None = None
    has_run_py: bool = False

    @property
    def parameter_names(self) -> list[str]:
        return [p.name for p in self.parameters]

    def validate(self, args: dict[str, Any]) -> tuple[bool, list[str]]:
        """Return (ok, missing_required_params)."""
        provided = set(args.keys())
        missing = [
            p.name
            for p in self.parameters
            if p.required and p.default is None and p.name not in provided
        ]
        return (not missing, missing)
