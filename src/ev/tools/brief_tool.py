"""Cross-project morning/now brief tool."""

from datetime import UTC, datetime, timedelta

from ev.memory.status import build_status_summary

from .registry import Tool


class BriefTool(Tool):
    """Tier-0 read-only tool that aggregates status across active projects."""

    def __init__(self, stale_days: int = 7):
        super().__init__(
            name="brief",
            tier=0,
            description="Get a concise cross-project status brief",
        )
        self.stale_days = stale_days

    def bind_store(self, store):
        self.store = store

    async def run(self) -> str:
        projects = await self.store.list_active_projects()
        if not projects:
            return "EV: no active projects in memory."

        lines: list[str] = []
        now = datetime.now(UTC)
        stale_threshold = now - timedelta(days=self.stale_days)

        for project in projects:
            summary = await build_status_summary(self.store, project.name)
            if "error" in summary:
                continue
            line = f"- {summary['name']} is at {summary['phase'] or 'unknown phase'}."
            if summary["open_issue_count"]:
                line += f" {summary['open_issue_count']} open issue(s)."
            if summary["open_pr_count"]:
                line += f" {summary['open_pr_count']} open PR(s)."
            if summary["recent_note_count"]:
                line += f" {summary['recent_note_count']} recent note(s)."

            last = summary.get("last_activity")
            is_stale = True
            if last:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=UTC)
                is_stale = last_dt < stale_threshold
            if is_stale:
                line += " (stale)"
            lines.append(line)

        header = f"EV brief — {len(projects)} active project(s):"
        return "\n".join([header, *lines])
