"""Hi-EV tools package.

Importing this package triggers auto-discovery of all tool modules so they can
self-register in the global plugin registry.
"""

from pathlib import Path

from ev.core.discovery import discover_package
from ev.tools.registry import ToolRegistry

# Trigger decorator registration for every tool module.
discover_package("ev.tools", Path(__file__).resolve().parent)

from .registry import Tool, ToolRegistry  # noqa: E402
from .status_tool import StatusTool  # noqa: E402

__all__ = ["Tool", "ToolRegistry", "StatusTool"]
