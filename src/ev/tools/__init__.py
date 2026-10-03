"""Hi-EV tools package.

Importing this package triggers auto-discovery of all tool modules so they can
self-register in the global plugin registry.
"""

from pathlib import Path

from ev.core.discovery import discover_package

# Trigger decorator registration for every tool module.
discover_package("ev.tools", Path(__file__).resolve().parent)

from .registry import Tool, ToolRegistry
from .status_tool import StatusTool

__all__ = ["StatusTool", "Tool", "ToolRegistry"]
