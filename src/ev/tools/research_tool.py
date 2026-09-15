"""Web research tool: DuckDuckGo search + NVIDIA LLM synthesis with citations."""

import hashlib
import json
from datetime import timedelta
from typing import Any

import redis.asyncio as redis

from ev.config import get_settings
from ev.llm.client import LLMClient
from ev.research.search import DuckDuckGoSearch

from .registry import Tool


class ResearchTool(Tool):
    """Tier-0 read-only web research tool with LLM-synthesized citations."""

    def __init__(self, max_results: int = 5, cache_ttl_seconds: int = 3600):
        super().__init__(
            name="research",
            tier=0,
            description="Search the web and synthesize a cited answer",
        )
        self.search = DuckDuckGoSearch(max_results=max_results)
        self.llm = LLMClient()
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._redis: redis.Redis | bool | None = None

    def bind_store(self, store):
        self.store = store

    def _redis_client(self):
        if self._redis is None:
            url = get_settings().redis_url
            try:
                self._redis = redis.Redis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            except (ConnectionError, TimeoutError, OSError, redis.RedisError):
                self._redis = False
        return self._redis if isinstance(self._redis, redis.Redis) else None

    def _cache_key(self, query: str) -> str:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return f"research:{digest}"

    async def _maybe_read_cache(self, query: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            return None
        try:
            cached = await client.get(self._cache_key(query))
            if cached:
                return json.loads(cached)
        except (ConnectionError, redis.RedisError, json.JSONDecodeError):
            return None
        return None

    async def _maybe_write_cache(self, query: str, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if not client:
            return
        try:
            await client.set(
                self._cache_key(query),
                json.dumps(payload, default=str),
                ex=int(self.cache_ttl.total_seconds()),
            )
        except (ConnectionError, redis.RedisError):
            return

    @staticmethod
    def _build_prompt(query: str, sources: list[dict[str, str]]) -> str:
        source_texts = []
        for idx, source in enumerate(sources, 1):
            source_texts.append(
                f"[{idx}] {source['title']}\nURL: {source['url']}\n{source['snippet']}"
            )
        prompt = (
            f"Answer the question using only the provided web search results. "
            f"Cite sources with bracket numbers like [1]. Keep the answer concise.\n\n"
            f"Question: {query}\n\n"
            f"Search results:\n" + "\n\n".join(source_texts)
        )
        return prompt

    async def run(self, query: str) -> dict[str, Any]:
        cached = await self._maybe_read_cache(query)
        if cached:
            return cached

        sources = await self.search.search(query)
        if not sources:
            answer = "EV: I couldn't find any web results for that query."
            payload = {"query": query, "answer": answer, "sources": []}
            await self._maybe_write_cache(query, payload)
            return payload

        prompt = self._build_prompt(query, sources)
        answer = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )
        payload = {"query": query, "answer": answer, "sources": sources}
        await self._maybe_write_cache(query, payload)
        return payload
