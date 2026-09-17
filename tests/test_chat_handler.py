"""Tests for the WebSocket chat session / intent dispatcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


async def test_chat_ping_message(mock_ws):
    from ev.server.chat import ChatSession

    session = ChatSession(mock_ws)
    await session.handle_message({"type": "ping"})
    mock_ws.send_json.assert_awaited_once_with({"type": "pong"})


async def test_chat_empty_transcript(mock_ws):
    from ev.server.chat import ChatSession

    session = ChatSession(mock_ws)
    await session.handle_message({"type": "transcript", "text": "   "})
    mock_ws.send_json.assert_awaited_once_with({"type": "error", "message": "Empty transcript"})


@patch("ev.server.chat.LLMClient")
async def test_chat_routes_to_status_tool(mock_llm_client, mock_ws, seeded_db):
    from ev.server.chat import ChatSession

    llm = MagicMock()
    llm.complete = AsyncMock(
        side_effect=[
            '{"tool": "status", "args": {"project": "RoboCAD"}}',
        ]
    )
    mock_llm_client.return_value = llm

    session = ChatSession(mock_ws)
    await session.handle_message({"type": "transcript", "text": "status of RoboCAD"})

    calls = [c.args[0] for c in mock_ws.send_json.await_args_list]
    assert any(c.get("type") == "phase" and c.get("phase") == "thinking" for c in calls)
    assert any(c.get("type") == "delta" and "RoboCAD" in c.get("text", "") for c in calls)
    assert calls[-1] == {"type": "done"}


@patch("ev.server.chat.LLMClient")
async def test_chat_runs_tier_one_action(mock_llm_client, mock_ws):
    from ev.server.chat import ChatSession

    llm = MagicMock()
    llm.complete = AsyncMock(return_value='{"tool": "work", "args": {"project": "RoboCAD", "task": "fix test"}}')
    mock_llm_client.return_value = llm

    session = ChatSession(mock_ws)
    await session.handle_message({"type": "transcript", "text": "work on RoboCAD fix test"})

    calls = [c.args[0] for c in mock_ws.send_json.await_args_list]
    delta = next(c for c in calls if c.get("type") == "delta")
    # Tier-1 work_on auto-executes in the MVP web UI. It tries to spawn Claude Code,
    # which fails in tests, so we expect an error message rather than a confirmation prompt.
    assert "EV couldn't run" in delta["text"] or "Claude Code" in delta["text"]
    assert calls[-1] == {"type": "done"}


async def test_chat_refuses_high_tier_tool(mock_ws):
    """Tier 2/3 tools are refused in the web UI regardless of intent."""
    from ev.server.chat import ChatSession
    from ev.tools.registry import Tool

    class FakeT2Tool(Tool):
        def __init__(self):
            super().__init__("fake_t2", 2, "Test tier-2 tool")

        async def run(self, **kwargs):
            return "should not run"

    session = ChatSession(mock_ws)
    session._register_tools = lambda r: r.register(FakeT2Tool())

    # Bypass classification and run the tool directly.
    response = await session._run_tool("fake_t2", {})
    assert "needs explicit confirmation" in response


@patch("ev.server.chat.LLMClient")
async def test_chat_general_conversation(mock_llm_client, mock_ws):
    from ev.server.chat import ChatSession

    llm = MagicMock()
    llm.complete = AsyncMock(
        side_effect=[
            '{"tool": "chat", "args": {}}',
            "Hello, I am EV.",
        ]
    )
    mock_llm_client.return_value = llm

    session = ChatSession(mock_ws)
    await session.handle_message({"type": "transcript", "text": "hello"})

    calls = [c.args[0] for c in mock_ws.send_json.await_args_list]
    delta = next(c for c in calls if c.get("type") == "delta")
    assert "Hello, I am EV." in delta["text"]
    assert calls[-1] == {"type": "done"}
