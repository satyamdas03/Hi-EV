"""Obligations listing tool."""

from typing import Any

from .registry import Tool


class ObligationsTool(Tool):
    """Tier-0 read-only tool that lists open obligations."""

    def __init__(self):
        super().__init__(
            name="obligations",
            tier=0,
            description="List open obligations extracted from email and calendar",
        )

    def bind_store(self, store):
        self.store = store

    async def run(
        self,
        project_name: str | None = None,
        status: str | None = "open",
        overdue: bool = False,
    ) -> dict[str, Any]:
        rows = await self.store.list_obligations(
            status=status,
            project_name=project_name,
            overdue=overdue,
        )
        return {
            "obligations": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "description": o.description,
                    "due_date": o.due_date.isoformat() if o.due_date else None,
                    "status": o.status,
                    "project_name": o.project_name,
                }
                for o in rows
            ]
        }
