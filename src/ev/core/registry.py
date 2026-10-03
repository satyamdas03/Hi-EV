"""Generic decorator registry for Hi-EV plugins.

Pattern borrowed from OpenJarvis (https://github.com/open-jarvis/OpenJarvis):
every component self-registers by decorating its implementation class, and
central dispatchers discover instances by querying the registry. This makes
LLM engines, memory backends, tools, agents, and skills hot-swappable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RegistryBase[T]:
    """A typed registry of plugin implementations.

    Implementations register themselves by name via the `register` decorator
    or the `register_instance` method. Callers ask for a class by name and
    instantiate it themselves, or request a pre-registered singleton instance.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._classes: dict[str, type[T]] = {}
        self._instances: dict[str, T] = {}

    def register(
        self,
        name: str | None = None,
    ) -> Callable[[type[T]], type[T]]:
        """Class decorator that records an implementation under `name`.

        If no name is provided, the class name (without a "Backend"/"Tool"
        suffix) is used.
        """

        def decorator(cls: type[T]) -> type[T]:
            key = name or _normalize_name(cls.__name__)
            if key in self._classes:
                logger.warning("%s registry: overwriting %r with %r", self.name, key, cls)
            self._classes[key] = cls
            logger.debug("%s registry: registered %r", self.name, key)
            return cls

        return decorator

    def register_instance(self, name: str, instance: T) -> T:
        """Register a pre-built instance (useful for tools that need args)."""
        self._instances[name] = instance
        return instance

    def get_class(self, name: str) -> type[T]:
        """Return the implementation class for `name`."""
        try:
            return self._classes[name]
        except KeyError as exc:
            raise KeyError(f"{self.name} registry has no entry for {name!r}") from exc

    def get(self, name: str) -> T:
        """Return a registered instance, or instantiate the class once."""
        if name in self._instances:
            return self._instances[name]
        cls = self.get_class(name)
        instance = cls()
        self._instances[name] = instance
        return instance

    def has(self, name: str) -> bool:
        return name in self._classes or name in self._instances

    def list(self) -> list[str]:
        """Return all registered names, classes first then instances."""
        return sorted(set(self._classes) | set(self._instances))

    def classes(self) -> dict[str, type[T]]:
        return dict(self._classes)

    def instances(self) -> dict[str, T]:
        return dict(self._instances)


def _normalize_name(class_name: str) -> str:
    """Strip common implementation suffixes to produce a stable registry key.

    Examples:
        StatusTool -> status
        FasterWhisperBackend -> faster_whisper
        HybridMemory -> hybrid
        OrchestratorAgent -> orchestrator
    """
    for suffix in ("Backend", "Tool", "Memory", "Agent", "Engine", "Skill"):
        if class_name.endswith(suffix):
            return _camel_to_snake(class_name[: -len(suffix)])
    return _camel_to_snake(class_name)


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and name[i - 1].islower():
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


# Convenience singletons used by Hi-EV subsystems.
# These are populated lazily via decorators or explicitly at startup.
registry: dict[str, RegistryBase[Any]] = {
    "tool": RegistryBase[Any]("tool"),
    "agent": RegistryBase[Any]("agent"),
    "memory": RegistryBase[Any]("memory"),
    "engine": RegistryBase[Any]("engine"),
    "skill": RegistryBase[Any]("skill"),
}


def register(kind: str, name: str | None = None) -> Callable[[type[Any]], type[Any]]:
    """Register a class in one of the global registries.

    Args:
        kind: one of "tool", "agent", "memory", "engine", "skill".
        name: optional override for the registry key.
    """
    if kind not in registry:
        raise ValueError(f"Unknown registry kind: {kind!r}; expected one of {list(registry)}")
    return registry[kind].register(name)
