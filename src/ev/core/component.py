"""Abstract base classes for Hi-EV plugins.

Each subsystem (tool, agent, memory, engine, skill) derives from one of these
ABCs and registers via the decorator registries in `ev.core.registry`. This
lets the daemon, CLI, and chat session discover capabilities without hard-coded
imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


class BaseTool(ABC):
    """A callable Hi-EV capability with a name, tier, and description."""

    name: str
    tier: int = 0
    description: str = ""
    accepts_store: bool = True

    async def setup(self, store: Any | None = None) -> None:
        """Called once before the tool is used, usually to bind a memory store."""
        if store is not None and self.accepts_store:
            self.bind_store(store)

    def bind_store(self, store: Any) -> None:
        """Attach a MemoryStore instance if the tool needs database access."""

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool. Must be implemented by subclasses."""


class BaseMemory(ABC):
    """Abstract backend for storing and retrieving personal context."""

    name: str

    @abstractmethod
    async def store(self, content: str, *, source: str = "", metadata: dict[str, Any] | None = None) -> str:
        """Persist content and return its memory id."""

    @abstractmethod
    async def retrieve(self, query: str, *, top_k: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        """Return relevant memory records for `query`."""


class BaseEngine(ABC):
    """Abstract LLM inference engine (cloud or local)."""

    name: str
    provider: str = ""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Return a non-streaming completion."""

    @abstractmethod
    async def complete_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Yield completion deltas."""


@dataclass
class AgentContext:
    """Runtime context passed to every agent run."""

    messages: list[dict[str, str]] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)
    store: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Structured output from an agent run."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    route: str | None = None


class BaseAgent(ABC):
    """An agent implementation that accepts context and returns a result."""

    name: str

    @abstractmethod
    async def run(self, input_text: str, context: AgentContext | None = None) -> AgentResult:
        """Execute the agent and return a structured result."""


class BaseSkill(ABC):
    """A reusable capability package described by a SKILL.md manifest.

    Concrete skills are usually thin wrappers loaded by the SkillManager; this
    ABC exists for runtime skill classes that need custom Python logic.
    """

    name: str
    description: str = ""

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the skill."""
