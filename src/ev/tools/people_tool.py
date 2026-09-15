"""People listing tool."""

from typing import Any

from .registry import Tool


class PeopleTool(Tool):
    """Tier-0 read-only tool that lists known people."""

    def __init__(self, limit: int = 100):
        super().__init__(
            name="people",
            tier=0,
            description="List people EV knows from Gmail and Calendar",
        )
        self.limit = limit

    def bind_store(self, store):
        self.store = store

    async def run(self, project_name: str | None = None, limit: int | None = None) -> dict[str, Any]:
        people = await self.store.list_people(project_name=project_name, limit=limit or self.limit)
        return {
            "people": [
                {
                    "email": p.email,
                    "name": p.name,
                    "source": p.source,
                    "last_contact_at": p.last_contact_at.isoformat() if p.last_contact_at else None,
                }
                for p in people
            ]
        }
