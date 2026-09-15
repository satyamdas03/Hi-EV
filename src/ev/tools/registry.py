"""Tool registry for Hi-EV capabilities."""

from typing import Any


class Tool:
    """Base class for a callable Hi-EV capability."""

    def __init__(self, name: str, tier: int, description: str):
        self.name = name
        self.tier = tier
        self.description = description

    async def run(self, **kwargs) -> Any:
        raise NotImplementedError


class ToolRegistry:
    """Holds and dispatches registered tools."""

    def __init__(self, store):
        self.store = store
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        if hasattr(tool, "bind_store"):
            tool.bind_store(self.store)

    def get(self, name: str) -> Tool:
        return self._tools[name]
