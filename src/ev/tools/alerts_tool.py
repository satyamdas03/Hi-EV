"""Proactive alert digest tool."""

from datetime import UTC, datetime
from typing import Any

from .deadline_watcher import DeadlineWatcherTool
from .registry import Tool


class AlertsTool(Tool):
    """Tier-0 read-only tool that returns the current urgent alert digest."""

    def __init__(self, urgent_hours: int = 72):
        super().__init__(
            name="alerts",
            tier=0,
            description="Return urgent deadline and obligation digest",
        )
        self.urgent_hours = urgent_hours

    def bind_store(self, store):
        self.store = store
        self.watcher = DeadlineWatcherTool(urgent_hours=self.urgent_hours)
        self.watcher.bind_store(store)

    async def run(self, project_name: str | None = None) -> dict[str, Any]:
        watch = await self.watcher.run(project_name=project_name)
        urgent = watch["urgent"]
        counts = watch["counts"]
        now = datetime.now(UTC).isoformat()

        if not urgent:
            return {
                "now": now,
                "digest": "EV: no urgent deadlines. Everything looks calm.",
                "urgent": [],
                "counts": counts,
            }

        lines = [f"EV alert — {counts['urgent']} urgent deadline(s):"]
        for item in urgent[:10]:
            lines.append(f"- {item['title']} (due {item['due_date'][:16]}, {item['priority']})")
        if counts["overdue"]:
            lines.append(f"⚠️ {counts['overdue']} overdue.")

        # Optional: include open obligations
        obligations = await self.store.list_obligations(status="open", overdue=True)
        if obligations:
            lines.append(f"\n{len(obligations)} open overdue obligation(s).")

        return {
            "now": now,
            "digest": "\n".join(lines),
            "urgent": urgent,
            "counts": counts,
            "overdue_obligations": len(obligations),
        }
