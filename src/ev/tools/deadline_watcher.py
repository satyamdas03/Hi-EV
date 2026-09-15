"""Deadline watcher: surface overdue, today, this-week, and future deadlines."""

from datetime import UTC, datetime, timedelta
from typing import Any

from .registry import Tool


class DeadlineWatcherTool(Tool):
    """Tier-0 read-only tool that ranks deadlines by urgency."""

    def __init__(self, urgent_hours: int = 72):
        super().__init__(
            name="deadline_watcher",
            tier=0,
            description="Rank deadlines by urgency into overdue/today/week/future buckets",
        )
        self.urgent_hours = urgent_hours

    def bind_store(self, store):
        self.store = store

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    async def run(self, project_name: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        week_end = now + timedelta(days=7)
        horizon = now + timedelta(hours=self.urgent_hours)

        deadlines = await self.store.get_upcoming_deadlines(status="open")
        if project_name is not None:
            tag = project_name.lower()
            deadlines = [d for d in deadlines if d.project_name == tag]

        overdue = []
        today = []
        this_week = []
        future = []
        urgent = []

        for d in deadlines:
            if d.due_date is None:
                continue
            due = self._as_utc(d.due_date)
            # Treat snoozed deadlines as not visible unless snooze expired
            if d.snooze_until:
                snooze = self._as_utc(d.snooze_until)
                if snooze > now:
                    continue
            entry = {
                "id": str(d.id),
                "title": d.title,
                "due_date": due.isoformat(),
                "priority": d.priority,
                "project_name": d.project_name,
            }
            if due < now:
                overdue.append(entry)
                urgent.append(entry)
            elif due <= today_end:
                today.append(entry)
                urgent.append(entry)
            elif due <= week_end:
                this_week.append(entry)
                if due <= horizon:
                    urgent.append(entry)
            else:
                future.append(entry)
                if due <= horizon:
                    urgent.append(entry)

        return {
            "now": now.isoformat(),
            "urgent_hours": self.urgent_hours,
            "project_name": project_name,
            "overdue": overdue,
            "today": today,
            "this_week": this_week,
            "future": future,
            "urgent": urgent,
            "counts": {
                "overdue": len(overdue),
                "today": len(today),
                "this_week": len(this_week),
                "future": len(future),
                "urgent": len(urgent),
                "total": len(deadlines),
            },
        }
