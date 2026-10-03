"""Adapter that exposes a loaded skill as a Hi-EV tool.

`SkillTool` renders the skill's prompt body with provided arguments, optionally
executes an associated `run.py` in a sandboxed subprocess, and returns the
result. This makes every discovered skill callable from the orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from ev.core.component import BaseTool
from ev.llm.client import LLMClient
from ev.skills.types import SkillManifest

logger = logging.getLogger(__name__)


class SkillTool(BaseTool):
    """Tool wrapper for a runtime skill manifest."""

    accepts_store = True

    def __init__(self, manifest: SkillManifest, client: LLMClient | None = None):
        self.manifest = manifest
        self.name = manifest.name
        self.tier = 1  # Default to reversible-write tier; skills never auto-run T2/T3.
        self.description = manifest.description or f"Skill: {manifest.name}"
        self.client = client or LLMClient()
        self.store: Any | None = None

    def bind_store(self, store: Any) -> None:
        self.store = store

    async def setup(self, store: Any | None = None) -> None:
        self.bind_store(store)

    async def run(self, **kwargs: Any) -> Any:
        ok, missing = self.manifest.validate(kwargs)
        if not ok:
            return {
                "error": f"Missing required parameters for skill '{self.name}': {', '.join(missing)}",
                "parameters": self.manifest.parameter_names,
            }

        if self.manifest.has_run_py and self.manifest.source_dir:
            return await self._run_python(kwargs)
        return await self._render_prompt(kwargs)

    async def _render_prompt(self, args: dict[str, Any]) -> dict[str, Any]:
        body = self.manifest.body
        try:
            rendered = body.format(**args)
        except KeyError as exc:
            return {"error": f"Missing placeholder in skill body: {exc}", "skill": self.name}

        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": rendered},
        ]
        try:
            text = await self.client.complete(messages, temperature=0.7, max_tokens=1024)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skill %s LLM call failed: %s", self.name, exc)
            return {"error": f"Skill '{self.name}' failed: {exc}"}

        return {
            "skill": self.name,
            "text": text.strip(),
            "rendered": rendered,
        }

    async def _run_python(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the skill's run.py in a hardened subprocess.

        The script receives arguments as a JSON blob on stdin and must print a
        JSON result to stdout. This is intentionally restrictive: only modules
        in the allow-list can be imported, and the subprocess runs with `-I -B -S`.
        """
        if not self.manifest.source_dir:
            return {"error": f"Skill '{self.name}' has no source directory"}

        run_py = self.manifest.source_dir / "run.py"
        if not run_py.exists():
            return {"error": f"Skill '{self.name}' missing run.py"}

        import json

        payload = json.dumps({"args": args, "store": None}).encode("utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(run_py),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(payload)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Skill '{self.name}' execution failed: {exc}"}

        if proc.returncode != 0:
            return {
                "error": f"Skill '{self.name}' exited with code {proc.returncode}",
                "stderr": stderr.decode("utf-8", errors="ignore")[:500],
            }

        try:
            result = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError:
            return {
                "skill": self.name,
                "text": stdout.decode("utf-8", errors="ignore").strip(),
            }
        return result

    def _system_prompt(self) -> str:
        return (
            "You are a skill executor for EV, a local-first personal AI. "
            "Follow the user's skill instructions precisely and return only the requested output."
        )
