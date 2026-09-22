"""Tier-1 reversible drafting tools: commit, PR, email reply."""

import asyncio
import subprocess
from typing import Any

from ev.llm.client import LLMClient

from .registry import Tool


class DraftTool(Tool):
    """Base class for Tier-2 drafting tools."""

    def __init__(self, name: str, description: str):
        super().__init__(name=name, tier=2, description=description)
        self._llm = LLMClient()
        self.store = None

    def bind_store(self, store):
        self.store = store

    async def _draft(self, prompt: str) -> str:
        return await self._llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )

    async def _log(self, project_name: str | None, event_type: str, description: str) -> None:
        if self.store and project_name:
            await self.store.add_event(project_name, event_type, description)


class DraftCommitTool(DraftTool):
    """Draft a commit message from staged changes."""

    def __init__(self):
        super().__init__(name="draft_commit", description="Draft a commit message from staged diff")

    async def run(self, project: str) -> dict[str, Any]:
        project_obj = await self.store.get_or_create_project(project)
        if not project_obj.repo_path:
            return {"error": f"No local repo path configured for {project}"}

        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "diff", "--cached"],
            cwd=project_obj.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        diff = result.stdout.strip()
        if not diff:
            return {"error": "No staged changes to draft a commit message from"}

        prompt = (
            "Draft a concise, conventional-commit-style commit message for the following staged diff. "
            "Use imperative mood. Keep the subject line under 72 characters.\n\n```\n"
            + diff
            + "\n```"
        )
        draft = await self._draft(prompt)
        await self._log(project, "draft_commit", "Drafted commit message from staged diff")
        return {"draft": draft, "tier": self.tier, "project": project}


class DraftPrTool(DraftTool):
    """Draft a PR title and body from the current branch diff vs main."""

    def __init__(self):
        super().__init__(name="draft_pr", description="Draft a PR title and body from branch diff")

    async def run(self, project: str) -> dict[str, Any]:
        project_obj = await self.store.get_or_create_project(project)
        if not project_obj.repo_path:
            return {"error": f"No local repo path configured for {project}"}

        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "diff", "main...HEAD"],
            cwd=project_obj.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        diff = result.stdout.strip()
        if not diff:
            # Fallback: compare against origin/main.
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "diff", "origin/main...HEAD"],
                cwd=project_obj.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            diff = result.stdout.strip()
        if not diff:
            return {"error": "No branch diff found to draft a PR from"}

        prompt = (
            "Draft a PR title and body for the following branch diff. "
            "Return a title on the first line, then a blank line, then the body.\n\n```\n"
            + diff
            + "\n```"
        )
        draft = await self._draft(prompt)
        await self._log(project, "draft_pr", "Drafted PR from branch diff")
        return {"draft": draft, "tier": self.tier, "project": project}


class DraftReplyTool(DraftTool):
    """Draft an email reply from a thread snippet."""

    def __init__(self):
        super().__init__(name="draft_reply", description="Draft a reply email in the user's voice")

    async def run(
        self,
        to: str,
        subject: str,
        thread_snippet: str,
        style_notes: str = "Be concise, warm, and professional.",
    ) -> dict[str, Any]:
        prompt = (
            f"Draft a reply email to {to} about the subject '{subject}'.\n"
            f"Style: {style_notes}\n\n"
            f"Original message snippet:\n{thread_snippet}\n\n"
            f"Draft only the reply body."
        )
        draft = await self._draft(prompt)
        await self._log(None, "draft_reply", f"Drafted reply to {to}")
        return {"draft": draft, "tier": self.tier, "to": to, "subject": subject}
