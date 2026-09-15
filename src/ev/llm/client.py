"""Thin, provider-agnostic async LLM client for Hi-EV."""

from typing import Any

import httpx

from ev.config import Settings, get_settings


class LLMClientError(Exception):
    """Raised when the LLM client cannot complete a request."""


def _default_model(provider: str) -> str:
    defaults = {
        "nvidia": "meta/llama-3.2-11b-vision-instruct",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
    }
    return defaults.get(provider, "meta/llama-3.2-11b-vision-instruct")


class LLMClient:
    """Async wrapper over NVIDIA NIM / OpenAI / Anthropic chat APIs."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.provider = (self.settings.llm_provider or "nvidia").lower()
        self.model = self.settings.llm_model or _default_model(self.provider)

    def _require_key(self, secret) -> str:
        if secret is None:
            raise LLMClientError(f"Missing API key for provider '{self.provider}'")
        return secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider == "nvidia":
            headers["Authorization"] = f"Bearer {self._require_key(self.settings.nvidia_api_key)}"
        elif self.provider == "openai":
            headers["Authorization"] = f"Bearer {self._require_key(self.settings.openai_api_key)}"
        elif self.provider == "anthropic":
            headers["x-api-key"] = self._require_key(self.settings.anthropic_api_key)
            headers["anthropic-version"] = "2023-06-01"
        else:
            raise LLMClientError(f"Unsupported LLM provider: {self.provider}")
        return headers

    def _url(self) -> str:
        if self.provider == "nvidia":
            base = self.settings.nvidia_base_url or "https://integrate.api.nvidia.com/v1"
            return f"{base}/chat/completions"
        if self.provider == "openai":
            return "https://api.openai.com/v1/chat/completions"
        if self.provider == "anthropic":
            return "https://api.anthropic.com/v1/messages"
        raise LLMClientError(f"Unsupported LLM provider: {self.provider}")

    def _body(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return body

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float = 60.0,
    ) -> str:
        """Send a chat completion request and return the assistant message content."""
        url = self._url()
        headers = self._headers()
        body = self._body(messages, temperature, max_tokens)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        if self.provider == "anthropic":
            content = data.get("content", [{}])[0].get("text", "")
        else:
            choices = data.get("choices", [])
            if not choices:
                raise LLMClientError("LLM response contained no choices")
            message = choices[0].get("message", {})
            content = message.get("content") or message.get("reasoning_content") or ""
        return content.strip()
