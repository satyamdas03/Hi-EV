"""Pre-meeting / pre-deadline prep tool."""

from datetime import UTC, datetime, timedelta
from typing import Any

from ev.llm.client import LLMClient

from .registry import Tool


class CalendarPrepTool(Tool):
    """Tier-0 tool that builds a prep packet from nearby calendar deadlines."""

    def __init__(self, window_hours: int = 2):
        super().__init__(
            name="calendar_prep",
            tier=0,
            description="Build a prep packet for a given time using nearby deadlines",
        )
        self.window_hours = window_hours
        self._llm = LLMClient()

    def bind_store(self, store):
        self.store = store

    @staticmethod
    def _parse_time(time: str) -> datetime:
        if "T" in time:
            dt = datetime.fromisoformat(time)
            return dt.astimezone(UTC)
        # Treat as today's HH:MM
        hour, minute = map(int, time.split(":"))
        now = datetime.now(UTC)
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    async def run(self, time: str) -> dict[str, Any]:
        target = self._parse_time(time)
        after = target - timedelta(hours=self.window_hours)
        before = target + timedelta(hours=self.window_hours)
        deadlines = await self.store.get_upcoming_deadlines(after=after, before=before)
        if not deadlines:
            return {"time": target.isoformat(), "prep": "EV: no deadlines nearby.", "deadlines": []}

        deadline_texts = []
        for d in deadlines:
            due = d.due_date.isoformat() if d.due_date else "unknown"
            deadline_texts.append(f"- {d.title} (due {due}, priority {d.priority})")
        prompt = (
            f"The user has the following upcoming deadlines around {target.isoformat()}. "
            f"Write a concise prep paragraph suggesting what to prepare.\n\n"
            + "\n".join(deadline_texts)
        )
        prep = await self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=512,
        )
        return {
            "time": target.isoformat(),
            "prep": prep,
            "deadlines": [
                {
                    "title": d.title,
                    "due_date": d.due_date.isoformat() if d.due_date else None,
                    "priority": d.priority,
                }
                for d in deadlines
            ],
        }
