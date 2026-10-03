"""Core plugin architecture for Hi-EV.

Provides generic registries and abstract base classes so that tools, agents,
memory backends, LLM engines, and skills can be discovered and swapped without
editing central dispatchers.
"""

from ev.core.component import AgentContext, AgentResult, BaseAgent, BaseEngine, BaseMemory, BaseSkill, BaseTool
from ev.core.discovery import discover_all, discover_package
from ev.core.registry import RegistryBase, register, registry

__all__ = [
    "AgentContext",
    "AgentResult",
    "BaseAgent",
    "BaseEngine",
    "BaseMemory",
    "BaseSkill",
    "BaseTool",
    "RegistryBase",
    "discover_all",
    "discover_package",
    "register",
    "registry",
]
