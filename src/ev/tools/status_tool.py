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
        return summary["summary_text"]
