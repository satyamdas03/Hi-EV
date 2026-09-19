"""Notes vault ingestion source."""

import hashlib
from pathlib import Path
from typing import Any

from ev.config import Settings
from ev.security.boundary import Blocklist, personal_only_guard

from .base import IngestionSource


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class NotesIngestion(IngestionSource):
    """Ingest a folder of personal markdown notes."""

    def __init__(self, config: Settings):
        with personal_only_guard(config):
            self.root = Path(config.notes_path)
            self.blocklist = Blocklist.from_settings(config)

    async def ingest(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not self.root.exists():
            return records
        for path in self.root.rglob("*.md"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            rel = str(path.relative_to(self.root))
            if self.blocklist.is_blocked_repo(rel) or self.blocklist.is_blocked_account(rel):
                continue
            records.append(
                {
                    "source": "notes",
                    "source_id": str(path),
                    "content_hash": _hash(content),
                    "content": content,
                    "project_tag": self._guess_project_tag(content, rel),
                    "privacy_level": "personal",
                    "trusted": True,
                }
            )
        return records

    def _guess_project_tag(self, content: str, rel_path: str) -> str | None:
        lower = (content + " " + rel_path).lower()
        for keyword in ["robocad", "learningrobotics", "neuralquant", "hi-ev"]:
            if keyword in lower:
                return keyword
        return None
