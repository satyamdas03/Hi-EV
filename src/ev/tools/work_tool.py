"""Claude Code spawn tool for Tier-1 reversible work."""

import subprocess
from typing import Any

from ev.memory.status import build_status_summary

from .registry import Tool


class WorkTool(Tool):
    """Tier-1 tool that spawns Claude Code in a repo with task context."""

    def __init__(self):
        super().__init__(
            name="work_on",
            tier=1,
            description="Spawn Claude Code CLI in a project repo with prepared context",
        )

    def bind_store(self, store):
        self.store = store

    async def _build_context(self, project_name: str, task: str) -> str:
        summary = await build_status_summary(self.store, project_name)
        lines = [
            f"# EV Task Context",
            f"",
            f"Project: {project_name}",
            f"Task: {task}",
        ]
        if summary.get("phase"):
            lines.append(f"Phase: {summary['phase']}")
        if summary.get("latest_commits"):
            lines.append("\nRecent commits:")
            for commit in summary["latest_commits"][:3]:
                first_line = (commit.get("content") or "").splitlines()[0][:120]
                lines.append(f"- {first_line}")
        if summary.get("recent_notes"):
            lines.append("\nRecent notes:")
            for note in summary["recent_notes"][:2]:
                first_line = (note.get("content") or "").splitlines()[0][:120]
                lines.append(f"- {first_line}")
        if summary.get("open_issue_count"):
            lines.append(f"\nOpen issues: {summary['open_issue_count']}")
        if summary.get("open_pr_count"):
            lines.append(f"Open PRs: {summary['open_pr_count']}")
        lines.append("\nPlease begin work on the task above. Be concise and reversible.")
        return "\n".join(lines)

    async def run(self, project: str, task: str) -> dict[str, Any]:
        summary = await build_status_summary(self.store, project)
        if "error" in summary:
            return {"error": summary["error"]}

        project_obj = await self.store.get_or_create_project(project)
        repo_path = project_obj.repo_path
        if not repo_path:
            return {"error": f"No local repo path configured for {project}"}

        context = await self._build_context(project, task)
        try:
            process = subprocess.Popen(
                ["claude", "code"],
                cwd=repo_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if process.stdin:
                process.stdin.write(context)
                process.stdin.close()
        except Exception as exc:
            return {"error": f"Failed to spawn Claude Code: {exc}"}

        await self.store.add_event(
            project,
            "spawn_claude_code",
            f"Spawned Claude Code for task: {task}",
        )

        return {
            "project": project,
            "repo_path": repo_path,
            "task": task,
            "context_preview": context[:200],
            "pid": process.pid,
        }
