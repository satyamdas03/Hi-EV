"""Tool registry for Hi-EV capabilities."""

from typing import Any


class ToolTierError(Exception):
    """Raised when the requested tool exceeds the guard-enforced tier ceiling."""


class Tool:
    """Base class for a callable Hi-EV capability."""

    def __init__(self, name: str, tier: int, description: str):
        self.name = name
        self.tier = tier
        self.description = description

    async def run(self, **kwargs) -> Any:
        raise NotImplementedError


class ToolRegistry:
    """Holds and dispatches registered tools with optional guard enforcement."""

    def __init__(self, store):
        self.store = store
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        if hasattr(tool, "bind_store"):
            tool.bind_store(self.store)

    def get(self, name: str, guard_decision=None) -> Tool:
        """Return a tool by name, enforcing the guard's effective tier ceiling if provided."""
        tool = self._tools[name]
        if guard_decision is not None and tool.tier > guard_decision.max_tool_tier:
            raise ToolTierError(
                f"The '{name}' action is tier {tool.tier}, but this request is capped at "
                f"tier {guard_decision.max_tool_tier} due to guard policy."
            )
        return tool
