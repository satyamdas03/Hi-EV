"""Runtime skill discovery and catalog management for Hi-EV."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ev.config import Settings, get_settings
from ev.skills.parser import parse_skill_file
from ev.skills.types import SkillManifest

logger = logging.getLogger(__name__)


class SkillManager:
    """Discovers skills from configured directories and returns a catalog."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._skills: dict[str, SkillManifest] = {}

    def _skill_dirs(self) -> list[Path]:
        """Return candidate skill directories."""
        candidates: list[Path] = []
        if self.settings.skills_dir:
            candidates.append(Path(self.settings.skills_dir))
        # Built-in skills shipped with the repo.
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        candidates.append(repo_root / "skills")
        # Per-user skills in app data dir.
        candidates.append(Path(self.settings.app_data_dir) / "skills")
        return [p for p in candidates if p.exists() and p.is_dir()]

    def discover(self) -> dict[str, SkillManifest]:
        """Scan skill directories and build the catalog."""
        self._skills.clear()
        for directory in self._skill_dirs():
            for path in directory.rglob("SKILL.md"):
                manifest = parse_skill_file(path)
                if manifest is None:
                    continue
                if manifest.name in self._skills:
                    logger.warning(
                        "Skill %r already loaded from %s; skipping duplicate at %s",
                        manifest.name,
                        self._skills[manifest.name].source_dir,
                        manifest.source_dir,
                    )
                    continue
                self._skills[manifest.name] = manifest
                logger.debug("Discovered skill %r from %s", manifest.name, path)
        return dict(self._skills)

    def list(self) -> list[str]:
        return sorted(self._skills)

    def get(self, name: str) -> SkillManifest | None:
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        return name in self._skills

    def refresh(self) -> dict[str, SkillManifest]:
        """Clear the catalog and re-discover skills."""
        return self.discover()
