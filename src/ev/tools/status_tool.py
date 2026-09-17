"""Status tool implementation."""

from ev.memory.status import build_status_summary

from .registry import Tool


class StatusTool(Tool):
    """Tier-0 read-only tool that returns a one-paragraph project status."""

    def __init__(self):
        super().__init__(name="status", tier=0, description="Get a one-paragraph status update for a project")

    def bind_store(self, store):
        self.store = store

    async def run(self, project: str) -> str:
        summary = await build_status_summary(self.store, project)
        if "error" in summary:
            return f"EV: {summary['error']}"

        text = summary["summary_text"]
        memory_context = await self._fetch_memory_context(project)
        if memory_context:
            text += f"\n\nFrom memory:{memory_context}"
        return text

    async def _fetch_memory_context(self, project: str) -> str:
        try:
            chunks = await self.store.search_document_chunks(
                query=project,
                project_name=project.lower(),
                k=3,
            )
        except Exception:  # noqa: BLE001
            return ""
        if not chunks:
            return ""
        lines = [f"- {c['text'].replace(chr(10), ' ')[:140]}" for c in chunks]
        return "\n" + "\n".join(lines)
