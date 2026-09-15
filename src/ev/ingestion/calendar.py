"""Read-only Google Calendar ingestion source."""

import hashlib
from datetime import UTC, datetime
from typing import Any

from ev.config import Settings
from ev.security.boundary import assert_personal_only

from .base import IngestionSource


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_datetime(value: dict) -> datetime | None:
    if "dateTime" in value:
        dt = datetime.fromisoformat(value["dateTime"])
        return dt.astimezone(UTC)
    if "date" in value:
        return datetime.strptime(value["date"], "%Y-%m-%d").replace(tzinfo=UTC)
    return None


class CalendarIngestion(IngestionSource):
    """Ingest personal Google Calendar events read-only and extract deadlines, people, obligations."""

    def __init__(
        self,
        config: Settings,
        service: Any | None = None,
        project_tags: list[str] | None = None,
    ):
        assert_personal_only(config)
        if not config.google_enabled:
            raise RuntimeError("Calendar ingestion disabled; set EV_GOOGLE_ENABLED=true")
        self.service = service
        if self.service is None:
            from ev.google_auth import GoogleAuthHelper

            self.service = GoogleAuthHelper(config).get_service("calendar", "v3")
        self.project_tags = [tag.lower() for tag in (project_tags or [])]

    async def ingest(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        records: list[dict[str, Any]] = []
        deadlines: list[dict[str, Any]] = []
        people: list[dict[str, Any]] = []
        obligations: list[dict[str, Any]] = []
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        for event in events_result.get("items", []):
            content = self._format_event(event)
            project_tag = self._guess_project_tag(content)
            records.append(
                {
                    "source": "calendar_events",
                    "source_id": event.get("id", ""),
                    "content_hash": _hash(content),
                    "content": content,
                    "project_tag": project_tag,
                    "privacy_level": "sensitive",
                }
            )
            due = _parse_datetime(event.get("start", {}))
            if due:
                deadlines.append(
                    {
                        "title": event.get("summary", "Calendar event"),
                        "due_date": due,
                        "source": "calendar",
                        "source_id": event.get("id", ""),
                        "priority": "high" if self._is_deadline_like(event) else "medium",
                        "project_name": project_tag,
                    }
                )
                if self._is_obligation_like(event):
                    obligations.append(
                        {
                            "title": f"Prepare for: {event.get('summary', 'meeting')}",
                            "description": event.get("description", ""),
                            "due_date": due,
                            "source": "calendar",
                            "source_id": f"obl:{event.get('id', '')}",
                            "project_name": project_tag,
                            "status": "open",
                        }
                    )
            for attendee in event.get("attendees", []):
                person = self._extract_person(attendee)
                if person:
                    people.append(person)

        return records, deadlines, people, obligations

    def _format_event(self, event: dict) -> str:
        lines = [f"Event: {event.get('summary', '')}"]
        if event.get("description"):
            lines.append(f"Description: {event['description']}")
        start = event.get("start", {})
        end = event.get("end", {})
        if "dateTime" in start:
            lines.append(f"Start: {start['dateTime']}")
            lines.append(f"End: {end.get('dateTime', '')}")
        elif "date" in start:
            lines.append(f"Date: {start['date']}")
        if event.get("attendees"):
            lines.append(f"Attendees: {len(event['attendees'])}")
        return "\n".join(lines)

    def _is_deadline_like(self, event: dict) -> bool:
        summary = (event.get("summary", "") or "").lower()
        keywords = ["deadline", "due", "file", "submit", "payment", "patent"]
        return any(k in summary for k in keywords)

    def _is_obligation_like(self, event: dict) -> bool:
        summary = (event.get("summary", "") or "").lower()
        keywords = ["review", "sync", "prep", "follow-up", "action", "respond", "send", "draft", "meet", "call"]
        return any(k in summary for k in keywords)

    def _guess_project_tag(self, content: str) -> str | None:
        lower = content.lower()
        for tag in self.project_tags:
            if tag in lower:
                return tag
        for keyword in ["robocad", "learningrobotics", "neuralquant", "hi-ev", "patent"]:
            if keyword in lower:
                return keyword
        return None

    def _extract_person(self, attendee: dict) -> dict[str, Any] | None:
        email = (attendee.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return None
        name = attendee.get("displayName")
        return {
            "email": email,
            "name": name,
            "source": "calendar",
            "source_id": email,
            "last_contact_at": datetime.now(UTC),
        }
