"""Connect the skill catalog to the global tool registry.

`load_skills_into_registry` is called during daemon startup. It discovers skills
and registers a `SkillTool` adapter for each one so the orchestrator can invoke
them like any other tool.
"""

from __future__ import annotations

import logging

from ev.core import registry
from ev.skills.manager import SkillManager
from ev.skills.tool_adapter import SkillTool

logger = logging.getLogger(__name__)


def load_skills_into_registry(manager: SkillManager | None = None) -> list[str]:
    """Discover skills and register each as a tool. Returns the loaded names."""
    if manager is None:
        manager = SkillManager()
    manifests = manager.discover()
    loaded: list[str] = []
    for name, manifest in manifests.items():
        tool = SkillTool(manifest)
        registry["tool"].register_instance(name, tool)
        loaded.append(name)
        logger.debug("Registered skill tool %r", name)
    return loaded
