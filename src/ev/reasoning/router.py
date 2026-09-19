"""Reasoning router: choose fast / agent / deliberate path per request."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from ev.config import Settings, get_settings
from ev.llm.client import LLMClient


class Route(str, Enum):
    """Reasoning depth tiers."""

    FAST = "fast"
    AGENT = "agent"
    DELIBERATE = "deliberate"


@dataclass
class RequestContext:
    """Optional context for routing decisions."""

    available_tools: list[str] = field(default_factory=list)
    history_turns: int = 0
    source: str = "user"
    trusted: bool = True


@dataclass
class RouteDecision:
    """Structured routing decision returned by `route_request`."""

    path: Route
    reason: str
    confidence: float
    tools: list[str] = field(default_factory=list)
    cost_budget: int = 1
    latency_budget_ms: int = 2000


# Heuristic signals. Patterns are lower-cased before matching.
_FAST_KEYWORDS = [
    "status",
    "what is",
    "what's",
    "whats",
    "brief",
    "alerts",
    "deadlines",
    "remember",
    "memory",
    "who",
    "when",
    "where",
    "current phase",
    "how many",
    "list",
    "show me",
    "tell me",
    "what did i decide",
    "what did we decide",
    "what was decided",
]

_AGENT_KEYWORDS = [
    "prep",
    "prepare",
    "summarize",
    "across",
    "plan my",
    "schedule",
    "gather",
    "collect",
    "compile",
    "compare",
    "for each",
    "all my",
    "week",
    "day",
    "update me",
    "follow up",
    "follow-up",
    "draft",
    "research",
    "and",
    "then",
]

_DELIBERATE_KEYWORDS = [
    "should i ",
    "should we ",
    "what could break",
    "consequences",
    "trade-off",
    "tradeoff",
    "risk",
    "strategy",
    "decision",
    "impact",
    "worst case",
    "if i skip",
    "if we skip",
    "prioritize",
    "budget",
    "allocate",
    "choose between",
    "should we delay",
    "patent",
    "ip",
    "legal",
    "decide between",
    "decide whether",
    "decide if",
    "make a decision",
]

_LLM_ROUTE_PROMPT = (
    "You are a routing classifier for a personal AI assistant. "
    "Classify the user request into one of: fast, agent, deliberate.\n\n"
    "- fast: factual lookup, one tool call, low stakes (e.g., status, memory recall, brief).\n"
    "- agent: multi-step, needs several tools or context (e.g., prep, summarize across projects, plan my day).\n"
    "- deliberate: high stakes, trade-offs, consequences, planning (e.g., should I, what could break, risk, patent).\n\n"
    "Return ONLY a JSON object with no markdown: "
    '{"path":"fast|agent|deliberate","reason":"short reason","confidence":0.0-1.0}'
)


class Router:
    """Heuristic router with lightweight LLM fallback."""

    CONFIDENCE_THRESHOLD = 0.6

    def __init__(
        self,
        settings: Settings | None = None,
        client: LLMClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.client = client

    def route(
        self,
        query: str,
        context: RequestContext | None = None,
    ) -> RouteDecision:
        """Classify `query` into a reasoning path.

        Uses deterministic heuristics first and only invokes the LLM when
        heuristic confidence is below the threshold.
        """
        context = context or RequestContext()
        decision = self._heuristic(query, context)
        if decision.confidence >= self.CONFIDENCE_THRESHOLD:
            return decision
        return self._llm_fallback(query, context)

    def _heuristic(self, query: str, context: RequestContext) -> RouteDecision:
        lower = (query or "").lower()
        words = lower.split()
        word_count = len(words)

        deliberate_hits = sum(1 for p in _DELIBERATE_KEYWORDS if p in lower)
        agent_hits = sum(1 for p in _AGENT_KEYWORDS if p in lower)
        fast_hits = sum(1 for p in _FAST_KEYWORDS if p in lower)

        # High-stakes phrases override everything.
        if deliberate_hits:
            confidence = min(0.95, 0.65 + 0.1 * deliberate_hits)
            return RouteDecision(
                path=Route.DELIBERATE,
                reason=f"High-stakes language matched {deliberate_hits} signal(s).",
                confidence=confidence,
                cost_budget=3,
                latency_budget_ms=8000,
            )

        # Follow-up in an ongoing conversation usually needs context.
        if context.history_turns > 0:
            return RouteDecision(
                path=Route.AGENT,
                reason="Continuing an existing conversation; use agent context.",
                confidence=0.65,
                cost_budget=2,
                latency_budget_ms=5000,
            )

        # Multi-step / cross-cutting language -> agent.
        if agent_hits:
            # A long query with conjunctions strongly suggests multiple steps.
            confidence = min(0.9, 0.55 + 0.08 * agent_hits)
            if word_count > 25 and ("and" in lower or "," in query):
                confidence = max(confidence, 0.8)
            return RouteDecision(
                path=Route.AGENT,
                reason=f"Multi-step language matched {agent_hits} signal(s).",
                confidence=confidence,
                cost_budget=2,
                latency_budget_ms=5000,
            )

        # Short factual lookup with a keyword -> fast.
        if fast_hits:
            confidence = min(0.9, 0.6 + 0.1 * fast_hits)
            return RouteDecision(
                path=Route.FAST,
                reason=f"Factual lookup matched {fast_hits} signal(s).",
                confidence=confidence,
                cost_budget=1,
                latency_budget_ms=2000,
            )

        # Very short query without any keyword is ambiguous; let the LLM decide.
        if word_count <= 6:
            return RouteDecision(
                path=Route.FAST,
                reason="Very short query with no strong signal; will use LLM fallback.",
                confidence=0.4,
                cost_budget=1,
                latency_budget_ms=2000,
            )

        # Longer query without signal stays fast but with moderate confidence.
        return RouteDecision(
            path=Route.FAST,
            reason="No strong heuristic signal; defaulting to fast path.",
            confidence=0.55,
            cost_budget=1,
            latency_budget_ms=2000,
        )

    def _llm_fallback(self, query: str, context: RequestContext) -> RouteDecision:
        if not self.settings.enable_reasoning_router or not self.client:
            # If the router is disabled or no client is available, stay fast.
            return RouteDecision(
                path=Route.FAST,
                reason="LLM fallback disabled; defaulting to fast path.",
                confidence=0.5,
                cost_budget=1,
                latency_budget_ms=2000,
            )

        tools_hint = ""
        if context.available_tools:
            tools_hint = f"\nAvailable tools: {', '.join(context.available_tools)}"

        messages = [
            {"role": "system", "content": _LLM_ROUTE_PROMPT + tools_hint},
            {"role": "user", "content": query},
        ]
        try:
            # Run synchronously; the caller can await if they pass an async client.
            raw = self._run_sync(self.client.complete(messages, temperature=0.0, max_tokens=64))
            parsed = json.loads(raw)
            path = Route(parsed.get("path", "fast"))
            confidence = float(parsed.get("confidence", 0.6))
            reason = parsed.get("reason", "LLM fallback classification.")
        except Exception:  # noqa: BLE001
            return RouteDecision(
                path=Route.FAST,
                reason="LLM fallback failed; defaulting to fast path.",
                confidence=0.5,
                cost_budget=1,
                latency_budget_ms=2000,
            )

        budgets = {
            Route.FAST: (1, 2000),
            Route.AGENT: (2, 5000),
            Route.DELIBERATE: (3, 8000),
        }
        cost_budget, latency_budget_ms = budgets.get(path, (1, 2000))
        return RouteDecision(
            path=path,
            reason=reason,
            confidence=confidence,
            cost_budget=cost_budget,
            latency_budget_ms=latency_budget_ms,
        )

    @staticmethod
    def _run_sync(coro):
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        if loop.is_running():
            # Safe fallback for tests running inside an async event loop:
            # create a new loop in a thread. Avoids `RuntimeError: cannot be called from a running event loop`.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return asyncio.run(coro)


def route_request(
    query: str,
    context: RequestContext | None = None,
    settings: Settings | None = None,
    client: LLMClient | None = None,
) -> RouteDecision:
    """Convenience entry point: classify `query` into a reasoning path."""
    return Router(settings=settings, client=client).route(query, context)
