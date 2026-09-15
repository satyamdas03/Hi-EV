"""Read-only Gmail ingestion source."""

import hashlib
from typing import Any

from ev.config import Settings
from ev.security.boundary import Blocklist, assert_personal_only

from .base import IngestionSource


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


class GmailIngestion(IngestionSource):
    """Ingest personal Gmail messages read-only."""

    def __init__(self, config: Settings, service: Any | None = None):
        assert_personal_only(config)
        if not config.google_enabled:
            raise RuntimeError("Gmail ingestion disabled; set EV_GOOGLE_ENABLED=true")
        self.service = service
        if self.service is None:
            from ev.google_auth import GoogleAuthHelper

            self.service = GoogleAuthHelper(config).get_service("gmail", "v1")
        self.blocklist = Blocklist(
            work_handles=["financialsimplicity"],
            work_domains=["financialsimplicity.com"],
        )

    def _extract_text(self, message: dict) -> str:
        snippet = message.get("snippet", "")
        payload = message.get("payload", {})
        headers = payload.get("headers", [])
        parts = [f"From: {_header(headers, 'From')}"]
        subject = _header(headers, "Subject")
        if subject:
            parts.append(f"Subject: {subject}")
        date = _header(headers, "Date")
        if date:
            parts.append(f"Date: {date}")
        if snippet:
            parts.append(f"Snippet: {snippet}")
        body = self._body_text(payload)
        if body:
            parts.append(f"Body: {body[:2000]}")
        return "\n".join(parts)

    def _body_text(self, payload: dict) -> str:
        body = payload.get("body", {}).get("data", "")
        if body:
            import base64

            try:
                return base64.urlsafe_b64decode(body.encode("utf-8")).decode("utf-8", errors="ignore")
            except (ValueError, UnicodeDecodeError):
                return ""
        parts = payload.get("parts", [])
        texts = []
        for part in parts:
            if part.get("mimeType", "").startswith("text/"):
                data = part.get("body", {}).get("data", "")
                if data:
                    import base64

                    try:
                        texts.append(base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore"))
                    except (ValueError, UnicodeDecodeError):
                        pass
        return "\n".join(texts)

    async def ingest(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        response = self.service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=20).execute()
        messages = response.get("messages", [])
        for msg_meta in messages:
            message = self.service.users().messages().get(userId="me", id=msg_meta["id"]).execute()
            headers = message.get("payload", {}).get("headers", [])
            sender = _header(headers, "From")
            if self.blocklist.is_blocked_account(sender):
                continue
            content = self._extract_text(message)
            records.append(
                {
                    "source": "gmail_messages",
                    "source_id": message["id"],
                    "content_hash": _hash(content),
                    "content": content,
                    "project_tag": self._guess_project_tag(content),
                    "privacy_level": "sensitive",
                }
            )
        return records

    def _guess_project_tag(self, content: str) -> str | None:
        lower = content.lower()
        for keyword in ["robocad", "learningrobotics", "neuralquant", "hi-ev", "patent"]:
            if keyword in lower:
                return keyword if keyword != "patent" else "patent"
        return None
