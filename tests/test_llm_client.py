"""Tests for the Hi-EV LLM client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ev.config import Settings, get_settings
from ev.llm.client import LLMClient, LLMClientError


def _clear_settings_cache():
    get_settings.cache_clear()


async def test_llm_client_requires_nvidia_api_key():
    client = LLMClient(Settings(nvidia_api_key=None, llm_provider="nvidia"))
    with pytest.raises(LLMClientError):
        await client.complete(messages=[{"role": "user", "content": "hi"}])


@patch("ev.llm.client.httpx.AsyncClient")
async def test_llm_client_nvidia_request_body_and_response(mock_async_client):
    _clear_settings_cache()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Hello from NVIDIA"}}]
    }
    response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=response)
    mock_async_client.return_value = mock_client

    client = LLMClient(
        Settings(
            nvidia_api_key="nvapi-test",
            nvidia_base_url="https://integrate.api.nvidia.com/v1",
            llm_provider="nvidia",
            llm_model="meta/llama-3.2-11b-vision-instruct",
        )
    )
    result = await client.complete(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.5,
        max_tokens=512,
    )

    assert result == "Hello from NVIDIA"
    mock_client.post.assert_called_once()
    url, kwargs = mock_client.post.call_args
    assert url[0] == "https://integrate.api.nvidia.com/v1/chat/completions"
    body = kwargs["json"]
    assert body["model"] == "meta/llama-3.2-11b-vision-instruct"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["temperature"] == 0.5
    assert body["max_tokens"] == 512
    assert kwargs["headers"]["Authorization"] == "Bearer nvapi-test"


def _mock_stream_response(sse_lines):
    async def _lines():
        for line in sse_lines:
            yield line

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.aiter_lines = _lines
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@patch("ev.llm.client.httpx.AsyncClient")
async def test_llm_client_stream_openai_format(mock_async_client):
    _clear_settings_cache()

    sse_lines = [
        "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n",
        "data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}\n",
        "data: [DONE]\n",
    ]

    mock_client = _mock_stream_response(sse_lines)
    mock_async_client.return_value = mock_client

    client = LLMClient(
        Settings(
            nvidia_api_key="nvapi-test",
            nvidia_base_url="https://integrate.api.nvidia.com/v1",
            llm_provider="nvidia",
            llm_model="meta/llama-3.2-11b-vision-instruct",
        )
    )
    chunks = [chunk async for chunk in client.complete_stream(messages=[{"role": "user", "content": "hi"}])]

    assert chunks == ["Hello", " world"]
    mock_client.stream.assert_called_once()
    args, kwargs = mock_client.stream.call_args
    assert args[0] == "POST"
    assert kwargs["json"]["stream"] is True


@patch("ev.llm.client.httpx.AsyncClient")
async def test_llm_client_stream_anthropic_format(mock_async_client):
    _clear_settings_cache()

    sse_lines = [
        'data: {"type":"content_block_delta","delta":{"text":"Hi"}}\n',
        'data: {"type":"content_block_delta","delta":{"text":" there"}}\n',
        "data: [DONE]\n",
    ]

    mock_client = _mock_stream_response(sse_lines)
    mock_async_client.return_value = mock_client

    client = LLMClient(
        Settings(
            anthropic_api_key="sk-ant-test",
            llm_provider="anthropic",
            llm_model="claude-3-5-sonnet-20241022",
        )
    )
    chunks = [chunk async for chunk in client.complete_stream(messages=[{"role": "user", "content": "hi"}])]

    assert chunks == ["Hi", " there"]
