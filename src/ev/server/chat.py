"""WebSocket chat session for the Hi-EV web client.

Turns browser transcripts into Hi-EV tool calls (or general chat) and streams the
response back as WebSocket deltas.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ev.db.base import SessionLocal
from ev.llm.client import LLMClient
from ev.memory.store import MemoryStore
from ev.tools.alerts_tool import AlertsTool
from ev.tools.brief_tool import BriefTool
from ev.tools.calendar_prep_tool import CalendarPrepTool
from ev.tools.deadline_watcher import DeadlineWatcherTool
from ev.tools.draft_tools import DraftCommitTool, DraftPrTool, DraftReplyTool
from ev.tools.memory_tool import MemoryTool, RememberTool
from ev.tools.obligations_tool import ObligationsTool
from ev.tools.people_tool import PeopleTool
from ev.tools.prep_tool import PrepTool
from ev.tools.registry import ToolRegistry
from ev.tools.research_tool import ResearchTool
from ev.tools.status_tool import StatusTool
from ev.tools.work_tool import WorkTool

logger = logging.getLogger(__name__)


# T0 = read-only auto, T1 = reversible write auto, T2/T3 require confirmation.
TIER_CONFIRMATION = {2: True, 3: True}


# Map natural intent names returned by the LLM to the actual Tool.name values.
_INTENT_ALIASES = {
    "work": "work_on",
    "deadline": "deadline_watcher",
    "deadlines": "deadline_watcher",
    "calendar_prep": "calendar_prep",
    "search_memory": "memory",
    "find_memory": "memory",
    "recall": "memory",
    "remember": "remember",
    "save_memory": "remember",
}


class ChatSession:
    """One WebSocket connection's worth of state and dispatch logic."""

    def __init__(self, websocket):
        self.websocket = websocket
        self.client = LLMClient()
        self.history: list[dict[str, str]] = []
        self.system_prompt = (
            "You are EV, a local-first personal AI operating system. You are helpful, concise, "
            "and you only act on the user's personal projects and data. You refuse requests "
            "that touch work accounts, employer data, or any patent/IP-sensitive material."
        )

    async def handle_message(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")
        if msg_type == "transcript":
            await self._on_transcript(data.get("text", ""))
        elif msg_type == "ping":
            await self._send_json({"type": "pong"})
        else:
            await self._send_error(f"Unknown message type: {msg_type}")

    async def _on_transcript(self, text: str) -> None:
        if not text or not text.strip():
            await self._send_error("Empty transcript")
            return

        self.history.append({"role": "user", "content": text})
        await self._send_json({"type": "phase", "phase": "thinking"})

        try:
            response = await self._resolve(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chat resolution failed: %s", exc)
            response = f"EV had a problem handling that: {exc}"

        self.history.append({"role": "assistant", "content": response})
        # Keep history bounded.
        if len(self.history) > 20:
            self.history = self.history[-20:]

        await self._send_json({"type": "delta", "text": response})
        await self._send_json({"type": "done"})

    async def _resolve(self, text: str) -> str:
        raw_intent, args = await self._classify_intent(text)
        intent = _INTENT_ALIASES.get(raw_intent, raw_intent)

        if intent == "chat":
            return await self._answer_chat(text)

        return await self._run_tool(intent, args)

    async def _classify_intent(self, text: str) -> tuple[str, dict[str, Any]]:
        """Use the LLM to map a user utterance to a tool + arguments.

        Asks for a single JSON object to minimize format drift. Falls back to a
        direct answer ("chat") if parsing fails or no tool matches.
        """
        prompt = (
            "You are routing user speech for a local personal AI assistant.\n"
            "Map the utterance to the best matching tool and extract arguments.\n\n"
            "Available tools:\n"
            "- status(project: str)\n"
            "- brief()\n"
            "- memory(query: str, project?: str)\n"
            "- remember(text: str, project?: str)\n"
            "- research(query: str)\n"
            "- deadlines(project?: str)\n"
            "- alerts(project?: str)\n"
            "- people(project?: str)\n"
            "- obligations(project?: str)\n"
            "- prep(title?: str, time?: str)\n"
            "- work(project: str, task: str)\n"
            "- draft(type: 'commit'|'pr'|'reply', project?: str, to?: str, subject?: str, snippet?: str)\n"
            "- chat() — for general conversation not matching any tool\n\n"
            "Return ONLY a JSON object, no markdown, no prose:\n"
            '{"tool": "<tool_name>", "args": {<arguments>}}\n\n'
            "Example:\n"
            '{"tool": "status", "args": {"project": "RoboCAD"}}\n\n'
            f"User said: {text!r}"
        )
        try:
            raw = await self.client.complete(
                [{"role": "system", "content": "You return only valid JSON."},
                 {"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Intent classification failed: %s", exc)
            return "chat", {}

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return "chat", {}
            intent = str(parsed.get("tool", "chat")).lower()
            args = parsed.get("args", {})
            if not isinstance(args, dict):
                args = {}
            return intent, args
        except json.JSONDecodeError:
            logger.warning("Could not parse intent JSON: %s", raw)
            return "chat", {}

    async def _answer_chat(self, text: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
        ]
        return await self.client.complete(messages, temperature=0.7, max_tokens=1024)

    async def _run_tool(self, intent: str, args: dict[str, Any]) -> str:
        async with SessionLocal() as session:
            store = MemoryStore(session)
            registry = ToolRegistry(store)
            self._register_tools(registry)
            try:
                tool = registry.get(intent)
            except KeyError:
                return f"EV doesn't have a '{intent}' tool yet."

            # Refuse T2/T3 actions outright in the MVP web UI.
            if tool.tier in TIER_CONFIRMATION:
                return (
                    f"The '{intent}' action is tier {tool.tier} and needs explicit confirmation "
                    "in the CLI. I can't run it from the voice/web interface yet."
                )

            try:
                result = await tool.run(**args)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tool %s failed: %s", intent, exc)
                return f"EV couldn't run {intent}: {exc}"

            return self._format_result(intent, result)

    def _register_tools(self, registry: ToolRegistry) -> None:
        registry.register(StatusTool())
        registry.register(BriefTool())
        registry.register(MemoryTool())
        registry.register(RememberTool())
        registry.register(ResearchTool())
        registry.register(DeadlineWatcherTool())
        registry.register(AlertsTool())
        registry.register(PeopleTool())
        registry.register(ObligationsTool())
        registry.register(PrepTool())
        registry.register(CalendarPrepTool())
        registry.register(WorkTool())
        registry.register(DraftCommitTool())
        registry.register(DraftPrTool())
        registry.register(DraftReplyTool())

    def _format_result(self, intent: str, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            if "summary" in result:
                return result["summary"]
            if "brief" in result:
                return result["brief"]
            if "answer" in result:
                return result["answer"]
            if "draft" in result:
                return result["draft"]
            if "prep" in result:
                return result["prep"]
            if "summary_text" in result:
                return result["summary_text"]
        return json.dumps(result, indent=2, default=str)

    async def _send_json(self, payload: dict[str, Any]) -> None:
        await self.websocket.send_json(payload)

    async def _send_error(self, message: str) -> None:
        await self._send_json({"type": "error", "message": message})
