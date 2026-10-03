"""Tool registry for Hi-EV capabilities.

This module now layers the legacy `ToolRegistry` on top of the global plugin
registry (`ev.core.registry`) so existing call sites keep working while new
tools can self-register via the `@register("tool")` decorator.
"""

from __future__ import annotations

from typing import Any

from ev.core.component import BaseTool
from ev.core.registry import registry


class ToolTierError(Exception):
    """Raised when the requested tool exceeds the guard-enforced tier ceiling."""


class Tool(BaseTool):
    """Base class for a callable Hi-EV capability (legacy compatibility).

    New tools should derive from this and decorate the class with
    `@register("tool")` so they are discovered automatically.
    """

    def __init__(self, name: str, tier: int, description: str):
        self.name = name
        self.tier = tier
        self.description = description

    async def run(self, **kwargs: Any) -> Any:
        raise NotImplementedError


class ToolRegistry:
    """Holds and dispatches registered tools with optional guard enforcement.

    The registry now discovers tools automatically via `ev.core.discovery` and
    falls back to the global plugin registry for tools that self-register. You
    can still register instances explicitly with `register()`.
    """

    def __init__(self, store):
        self.store = store
        self._tools: dict[str, BaseTool] = {}
        self._loaded = False

    def _ensure_discovered(self) -> None:
        if self._loaded:
            return
        # Import discovery here to avoid circular imports at module load.
        from pathlib import Path

        from ev.core.discovery import discover_package

        discover_package("ev.tools", Path(__file__).resolve().parent)

        for name, cls in registry["tool"].classes().items():
            if name not in self._tools:
                try:
                    instance = cls()
                    self.register(instance)
                except Exception as exc:  # noqa: BLE001
                    import logging

                    logging.getLogger(__name__).warning("Auto-discovery failed for tool %r: %s", name, exc)
        self._loaded = True

    def register(self, tool: BaseTool) -> BaseTool:
        self._tools[tool.name] = tool
        if hasattr(tool, "bind_store"):
            tool.bind_store(self.store)
        if hasattr(tool, "setup"):
            try:
                import asyncio
                asyncio.get_running_loop()
                # Async setup will be run lazily; sync setup below covers most cases.
            except RuntimeError:
                pass
        return tool

    def get(self, name: str, guard_decision=None) -> BaseTool:
        """Return a tool by name, enforcing the guard's effective tier ceiling if provided."""
        self._ensure_discovered()
        if name not in self._tools:
            # Try to instantiate from the global registry if not already loaded.
            if registry["tool"].has(name):
                instance = registry["tool"].get(name)
                self.register(instance)
            else:
                raise KeyError(f"Unknown tool: {name!r}")
        tool = self._tools[name]
        if guard_decision is not None and tool.tier > guard_decision.max_tool_tier:
            raise ToolTierError(
                f"The '{name}' action is tier {tool.tier}, but this request is capped at "
                f"tier {guard_decision.max_tool_tier} due to guard policy."
            )
        return tool

    def has(self, name: str) -> bool:
        self._ensure_discovered()
        return name in self._tools or registry["tool"].has(name)

    def names(self) -> list[str]:
        self._ensure_discovered()
        return sorted(set(self._tools) | set(registry["tool"].list()))
