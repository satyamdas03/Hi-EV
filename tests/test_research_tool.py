"""Tests for the web research tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.tools.research_tool import ResearchTool


@pytest.fixture
async def store():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield MemoryStore(session)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


_SAMPLE_HTML = """
<html>
<body>
<div class="result results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title"><a class="result__a" href="https://example.com/one">Model Predictive Control</a></h2>
    <a class="result__url" href="https://example.com/one">example.com/one</a>
    <a class="result__snippet">MPC is widely used in robotics.</a>
  </div>
</div>
<div class="result results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title"><a class="result__a" href="https://example.com/two">Humanoid Gait</a></h2>
    <a class="result__url" href="https://example.com/two">example.com/two</a>
    <a class="result__snippet">Gait controllers use preview control.</a>
  </div>
</div>
</body>
</html>
"""


@patch("ev.research.search.httpx.AsyncClient")
@patch("ev.tools.research_tool.LLMClient")
async def test_research_tool_returns_cited_answer(mock_llm_client, mock_async_client, store):
    response = MagicMock()
    response.status_code = 200
    response.text = _SAMPLE_HTML
    response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=response)
    mock_async_client.return_value = mock_client

    llm_instance = MagicMock()
    llm_instance.complete = AsyncMock(return_value="Model predictive control (MPC) is an optimization-based control method [1][2].")
    mock_llm_client.return_value = llm_instance

    tool = ResearchTool()
    tool.bind_store(store)
    result = await tool.run(query="what is MPC for humanoid robots")

    assert "MPC" in result["answer"] or "predictive control" in result["answer"].lower()
    assert len(result["sources"]) == 2
    assert any(s["url"] == "https://example.com/one" for s in result["sources"])
    assert any(s["url"] == "https://example.com/two" for s in result["sources"])
    llm_instance.complete.assert_called_once()
    prompt = llm_instance.complete.call_args.kwargs["messages"][0]["content"]
    assert "https://example.com/one" in prompt
