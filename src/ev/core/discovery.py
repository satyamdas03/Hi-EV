"""Auto-discovery of plugins in named subpackages.

Importing a module is enough to trigger its decorators; this module walks a
package directory and imports every non-test Python file so that registries are
populated automatically at startup.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def discover_package(package_name: str, package_path: Path | None = None) -> None:
    """Import every module in `package_name` to trigger decorators."""
    try:
        package = importlib.import_module(package_name)
    except ImportError as exc:
        logger.warning("Could not import %s for discovery: %s", package_name, exc)
        return

    if package_path is None:
        if not hasattr(package, "__path__"):
            return
        paths = package.__path__
    else:
        paths = [str(package_path)]

    prefix = package_name + "."
    for finder, name, ispkg in pkgutil.iter_modules(paths, prefix):
        if ispkg:
            continue
        if name.endswith("_test") or name.startswith("test_"):
            continue
        try:
            importlib.import_module(name)
            logger.debug("Discovered %s", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Discovery failed for %s: %s", name, exc)


def discover_all() -> None:
    """Discover tools, agents, skills, and voice backends in one call."""
    import ev  # noqa: F401

    base = Path(__file__).resolve().parent.parent
    packages = {
        "ev.tools": base / "tools",
        "ev.agents": base / "agents",
        "ev.skills": base / "skills",
        "ev.voice": base / "voice",
    }
    for package_name, package_path in packages.items():
        if package_path.is_dir():
            discover_package(package_name, package_path)
