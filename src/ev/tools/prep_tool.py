"""Pre-meeting / pre-deadline prep tool."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select

from ev.db.models import Ingest
from ev.llm.client import LLMClient
from ev.memory.status import build_status_summary

from .registry import Tool


class PrepTool(Tool):
    """Tier-0 tool that synthesizes a prep packet for a meeting or deadline."""

    def __init__(self, window_hours: int = 24):
        super().__init__(
            name="prep",
            tier=0,
            description="Build a prep packet for a meeting or deadline using calendar, people, and project context",
        )
        self.window_hours = window_hours
        self._llm = LLMClient()

    def bind_store(self, store):
        self.store = store

    async def run(self, title: str | None = None, project_name: str | None = None, time: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC)
        target = self._parse_time(time) if time else now
        after = target - timedelta(hours=self.window_hours)
        before = target + timedelta(hours=self.window_hours)

        # Find matching calendar events near the target time.
        # Prefer the event's own start date (parsed from content) over ingestion time.
        stmt = (
            select(Ingest)
            .where(Ingest.source == "calendar_events")
            .order_by(desc(Ingest.updated_at))
        )
        result = await self.store.session.execute(stmt)
        events = result.scalars().all()

        def _near(e: Ingest) -> bool:
            event_dt = self._parse_event_time(e.content or "")
            if event_dt is None:
                event_dt = e.updated_at
            if event_dt is None:
                return False
            event_dt = self._as_utc(event_dt)
            return after <= event_dt <= before

        events = [e for e in events if _near(e)]
        if title:
            title_lower = title.lower()
            events = [e for e in events if title_lower in (e.content or "").lower()]

        if not events:
            return {
                "target": target.isoformat(),
                "prep": "EV: no matching calendar event found in the nearby window.",
                "event": None,
                "attendees": [],
                "recent_emails": [],
            }

        event = events[0]
        event_title = self._event_title(event.content or "")

        # People context
        attendee_emails = self._extract_attendee_emails(event.content or "")
        attendees = []
        recent_emails = []
        for email in attendee_emails[:10]:
            person = await self._find_person_by_email(email)
            if person:
                attendees.append({"email": person.email, "name": person.name})
            emails = await self.store.get_recent_emails(email, days=7, limit=3)
            recent_emails.extend([{"from": email, "snippet": e.content[:200]} for e in emails])

        # Project context
        project_context = ""
        if project_name:
            summary = await build_status_summary(self.store, project_name)
            if "error" not in summary:
                project_context = summary["summary_text"]

        # Semantic memory context for the event/project
        memory_snippets: list[str] = []
        try:
            memory_query = " ".join(filter(None, [event_title, project_name or ""]))
            chunks = await self.store.search_document_chunks(
                query=memory_query,
                project_name=project_name.lower() if project_name else None,
                k=3,
            )
            memory_snippets = [c["text"].replace("\n", " ")[:200] for c in chunks]
        except Exception:  # noqa: BLE001
            memory_snippets = []

        # Nearby obligations
        obligations = await self.store.list_obligations(status="open")
        nearby_obligations = [
            f"- {o.title} (due {self._as_utc(o.due_date).isoformat()[:16] if o.due_date else 'unknown'})"
            for o in obligations
            if o.due_date and after <= self._as_utc(o.due_date) <= before
        ]

        prompt = self._build_prompt(
            event_title=event_title,
            target=target.isoformat(),
            attendees=attendees,
            recent_emails=recent_emails,
            project_context=project_context,
            memory_snippets=memory_snippets,
            obligations=nearby_obligations,
        )
        prep = await self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=768,
        )

        return {
            "target": target.isoformat(),
            "event": {
                "title": event_title,
                "content": event.content,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None,
            },
            "attendees": attendees,
            "recent_emails": recent_emails,
            "obligations": nearby_obligations,
            "prep": prep,
        }

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @staticmethod
    def _parse_time(time: str) -> datetime:
        if "T" in time:
            dt = datetime.fromisoformat(time)
            return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
        hour, minute = map(int, time.split(":"))
        now = datetime.now(UTC)
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _event_title(self, content: str) -> str:
        for line in content.splitlines():
            if line.lower().startswith("event:"):
                return line.split(":", 1)[1].strip()
        return "Meeting"

    @staticmethod
    def _parse_event_time(content: str) -> datetime | None:
        for line in content.splitlines():
            if line.lower().startswith("start:"):
                value = line.split(":", 1)[1].strip()
                try:
                    dt = datetime.fromisoformat(value)
                    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
                except ValueError:
                    return None
            if line.lower().startswith("date:"):
                value = line.split(":", 1)[1].strip()
                try:
                    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    return None
        return None

    def _extract_attendee_emails(self, content: str) -> list[str]:
        import re

        emails = []
        for line in content.splitlines():
            if line.lower().startswith("attendees:"):
                # Attendee details live in the Person table, not the formatted text.
                continue
            found = re.findall(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", line)
            emails.extend(found)
        return list(dict.fromkeys(emails))

    async def _find_person_by_email(self, email: str):
        from sqlalchemy import select

        from ev.db.models import Person

        result = await self.store.session.execute(select(Person).where(Person.email == email.lower()))
        return result.scalar_one_or_none()

    def _build_prompt(
        self,
        event_title: str,
        target: str,
        attendees: list[dict],
        recent_emails: list[dict],
        project_context: str,
        memory_snippets: list[str],
        obligations: list[str],
    ) -> str:
        parts = [
            f"Prepare me for '{event_title}' at {target}.",
            "",
            "Attendees:",
        ]
        if attendees:
            for a in attendees:
                parts.append(f"- {a.get('name') or a['email']} ({a['email']})")
        else:
            parts.append("- No known attendees.")

        if project_context:
            parts.extend(["", f"Project context: {project_context}"])

        if memory_snippets:
            parts.extend(["", "Related memory:"])
            for snippet in memory_snippets[:5]:
                parts.append(f"- {snippet}")

        if recent_emails:
            parts.extend(["", "Recent emails from attendees:"])
            for e in recent_emails[:5]:
                parts.append(f"- {e['from']}: {e['snippet']}")

        if obligations:
            parts.extend(["", "Nearby obligations:"])
            parts.extend(obligations)

        parts.extend([
            "",
            "Please write a concise prep packet with:",
            "1. A 3-bullet agenda",
            "2. 2 suggested talking points",
            "3. 1–2 open questions",
        ])
        return "\n".join(parts)
