"""Tests for the Hi-EV reasoning router."""

import pytest

from ev.config import Settings
from ev.reasoning.router import (
    RequestContext,
    Route,
    Router,
    route_request,
)


@pytest.fixture
def router():
    settings = Settings(enable_reasoning_router=False)
    return Router(settings=settings)


# 20 representative queries covering fast / agent / deliberate.
ROUTER_CASES = [
    ("status of RoboCAD", Route.FAST),
    ("what phase is Hi-EV in?", Route.FAST),
    ("what did I decide about the motor controller?", Route.FAST),
    ("brief me", Route.FAST),
    ("any alerts?", Route.FAST),
    ("show me my deadlines", Route.FAST),
    ("who is Satyam?", Route.FAST),
    ("how many open issues does RoboCAD have?", Route.FAST),
    ("what is the current phase of LearningRobotics?", Route.FAST),
    ("remember I chose stainless steel", Route.FAST),
    ("prep me for my 4pm call", Route.AGENT),
    ("summarize my week across projects", Route.AGENT),
    ("plan my day and draft any needed replies", Route.AGENT),
    ("gather updates from RoboCAD and Hi-EV", Route.AGENT),
    ("compare this week to last week", Route.AGENT),
    ("should I delay Phase 23 for the patent?", Route.DELIBERATE),
    ("what could break if I skip thermal testing?", Route.DELIBERATE),
    ("how should I allocate the budget between hardware and compute?", Route.DELIBERATE),
    ("should we use aluminium or carbon fiber for the arm?", Route.DELIBERATE),
    ("what are the trade-offs of moving to ROS2?", Route.DELIBERATE),
]


@pytest.mark.parametrize("query,expected", ROUTER_CASES)
def test_router_heuristic_classifies_queries(router, query, expected):
    decision = router.route(query)
    assert decision.path == expected, f"{query!r} routed to {decision.path}: {decision.reason}"
    assert 0.5 <= decision.confidence <= 1.0


def test_fast_path_budget(router):
    decision = router.route("status of RoboCAD")
    assert decision.path == Route.FAST
    assert decision.cost_budget == 1
    assert decision.latency_budget_ms == 2000


def test_agent_path_budget(router):
    decision = router.route("prep me for my 4pm call")
    assert decision.path == Route.AGENT
    assert decision.cost_budget == 2
    assert decision.latency_budget_ms == 5000


def test_deliberate_path_budget(router):
    decision = router.route("should I delay Phase 23 for the patent?")
    assert decision.path == Route.DELIBERATE
    assert decision.cost_budget == 3
    assert decision.latency_budget_ms == 8000


def test_untrusted_query_defaults_to_fast_without_llm():
    settings = Settings(enable_reasoning_router=False)
    decision = Router(settings=settings).route("foo bar baz", RequestContext(trusted=False))
    # No strong signal and LLM fallback disabled, so default fast.
    assert decision.path == Route.FAST
    assert "defaulting" in decision.reason.lower()


def test_route_request_entry_point(router):
    decision = route_request("brief me", settings=router.settings)
    assert decision.path == Route.FAST


@pytest.mark.asyncio
async def test_llm_fallback_uses_client_when_heuristic_is_weak():
    """When heuristic confidence is low and the router is enabled, ask the LLM."""

    class FakeLLMClient:
        async def complete(self, messages, **kwargs):
            return '{"path":"agent","reason":"needs prep + research","confidence":0.85}'

    settings = Settings(enable_reasoning_router=True)
    router = Router(settings=settings, client=FakeLLMClient())
    decision = router.route("do the thing with the stuff")
    assert decision.path == Route.AGENT
    assert decision.confidence == 0.85
    assert decision.reason == "needs prep + research"
    assert decision.cost_budget == 2
    assert decision.latency_budget_ms == 5000


@pytest.mark.asyncio
async def test_llm_fallback_defaults_to_fast_on_json_failure():
    class FakeLLMClient:
        async def complete(self, messages, **kwargs):
            return "not json"

    settings = Settings(enable_reasoning_router=True)
    router = Router(settings=settings, client=FakeLLMClient())
    decision = router.route("do the thing with the stuff")
    assert decision.path == Route.FAST
    assert "failed" in decision.reason.lower()


@pytest.mark.asyncio
async def test_llm_fallback_defaults_to_fast_when_disabled():
    class FakeLLMClient:
        async def complete(self, messages, **kwargs):
            return '{"path":"deliberate","reason":"test","confidence":0.9}'

    settings = Settings(enable_reasoning_router=False)
    router = Router(settings=settings, client=FakeLLMClient())
    decision = router.route("do the thing with the stuff")
    assert decision.path == Route.FAST
    assert "disabled" in decision.reason.lower()


def test_history_turns_push_to_agent(router):
    decision = router.route("what about the other one?", RequestContext(history_turns=1))
    assert decision.path == Route.AGENT
