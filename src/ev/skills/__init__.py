"""Hi-EV skills package.

Skills are discoverable, self-describing capability packages defined by a
`SKILL.md` manifest (and optional `skill.toml` / `run.py`). The `SkillManager`
loads them at runtime and the `SkillTool` adapter exposes each skill as a tool
that the orchestrator can call.
"""

from ev.skills.loader import load_skills_into_registry
from ev.skills.manager import SkillManager
from ev.skills.types import SkillManifest

__all__ = ["SkillManager", "SkillManifest", "load_skills_into_registry"]
