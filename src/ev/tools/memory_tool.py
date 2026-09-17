"""Semantic memory search tool for Hi-EV."""

from typing import Any

from ev.memory.chunks import Chunker

from .registry import Tool


class MemoryTool(Tool):
    """Tier-0 read-only tool that searches the user's semantic memory."""

    def __init__(self, chunker: Chunker | None = None):
        super().__init__(
            name="memory",
            tier=0,
            description="Search the user's semantic memory for relevant snippets",
        )
        self.chunker = chunker or Chunker()

    def bind_store(self, store):
        self.store = store

    async def run(self, query: str, project_name: str | None = None, k: int = 5) -> dict[str, Any]:
        if not query or not query.strip():
            return {
                "query": query,
                "chunks": [],
                "text": "EV: please provide a query to search memory.",
            }

        chunks = await self.store.search_document_chunks(
            query=query.strip(),
            project_name=project_name,
            k=k,
        )

        return {
            "query": query,
            "chunks": chunks,
            "text": self._format_chunks(chunks),
        }

    @staticmethod
    def _format_chunks(chunks: list[dict[str, Any]]) -> str:
        if not chunks:
            return "EV has nothing in memory about that yet."

        lines = ["EV remembers:"]
        for chunk in chunks:
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "").replace("\n", " ")
            lines.append(f"- [{source}] {text}")
        return "\n".join(lines)


class RememberTool(Tool):
    """Tier-0 user-initiated write that stores a sentence in semantic memory."""

    def __init__(self, chunker: Chunker | None = None):
        super().__init__(
            name="remember",
            tier=0,
            description="Store a user sentence in semantic memory",
        )
        self.chunker = chunker or Chunker()

    def bind_store(self, store):
        self.store = store

    async def run(self, text: str, project_name: str | None = None) -> dict[str, Any]:
        if not text or not text.strip():
            return {"text": "EV: nothing to remember."}

        import hashlib

        normalized = text.strip()
        source_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
        chunks = [
            chunk.to_dict()
            for chunk in self.chunker.split(
                normalized,
                source="user_memory",
                source_id=source_id,
                project_name=project_name.lower() if project_name else None,
            )
        ]
        if not chunks:
            return {"text": "EV: nothing to remember."}

        ids = await self.store.upsert_document_chunks(chunks)
        return {
            "text": f"EV remembered that ({len(ids)} chunk{'s' if len(ids) != 1 else ''}).",
            "ids": ids,
        }
