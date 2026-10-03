"""Multi-turn tool-using orchestrator agent for Hi-EV.

The orchestrator classifies the user's intent, looks up the matching tool in the
global tool registry, executes it, and returns a structured result. It is the
agent equivalent of the monolithic `ChatSession._resolve_from_intent` loop, but
swappable via the plugin registry.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ev.core import BaseAgent, register
from ev.core.component import AgentContext, AgentResult
from ev.llm.client import LLMClient
from ev.security.guard import Guard
from ev.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@register("agent", "orchestrator")
class OrchestratorAgent(BaseAgent):
    """Route a user request to the best registered tool and run it."""

    name = "orchestrator"

    # Map natural intent names returned by the LLM to the actual tool.name values.
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

    _CLASSIFY_PROMPT = (
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
        '{"tool": "status", "args": {"project": "RoboCAD"}}'
    )

    def __init__(
        self,
        client: LLMClient | None = None,
        guard: Guard | None = None,
        max_turns: int = 5,
    ) -> None:
        self.client = client or LLMClient()
        self.guard = guard or Guard()
        self.max_turns = max_turns

    async def run(self, input_text: str, context: AgentContext | None = None) -> AgentResult:
        context = context or AgentContext()
        raw_intent, args = await self._classify_intent(input_text)
        intent = self._INTENT_ALIASES.get(raw_intent, raw_intent)

        if intent == "chat" or not intent:
            return await self._chat(input_text, context)

        # Guard check before tool execution.
        guard_decision = self.guard.check(input_text, source="user", trusted=True)
        if guard_decision.status.value == "blocked":
            return AgentResult(text=guard_decision.reason, route="blocked")

        try:
            registry = ToolRegistry(context.store)
            tool = registry.get(intent, guard_decision=guard_decision)
            result = await tool.run(**args)
            text = self._format_result(intent, result)
            return AgentResult(text=text, tool_calls=[{"tool": intent, "args": args}], route="agent")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Orchestrator tool %s failed: %s", intent, exc)
            return AgentResult(text=f"EV couldn't run {intent}: {exc}", route="agent")

    async def _classify_intent(self, text: str) -> tuple[str, dict[str, Any]]:
        messages = [
            {"role": "system", "content": "You return only valid JSON."},
            {"role": "user", "content": f"{self._CLASSIFY_PROMPT}\n\nUser said: {text!r}"},
        ]
        try:
            raw = await self.client.complete(messages, temperature=0.1, max_tokens=256)
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return "chat", {}
            intent = str(parsed.get("tool", "chat")).lower()
            args = parsed.get("args", {})
            if not isinstance(args, dict):
                args = {}
            return intent, args
        except json.JSONDecodeError:
            logger.warning("Could not parse orchestrator intent JSON: %s", raw)
            return "chat", {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Orchestrator intent classification failed: %s", exc)
            return "chat", {}

    async def _chat(self, text: str, context: AgentContext) -> AgentResult:
        messages = [
            {"role": "system", "content": self._system_prompt()},
            *context.messages,
            {"role": "user", "content": text},
        ]
        reply = await self.client.complete(messages, temperature=0.7, max_tokens=1024)
        return AgentResult(text=reply.strip(), route="fast")

    def _system_prompt(self) -> str:
        return (
            "You are EV, a local-first personal AI operating system. You are helpful, concise, "
            "and you only act on the user's personal projects and data. You refuse requests "
            "that touch work accounts, employer data, or any patent/IP-sensitive material."
        )

    def _format_result(self, intent: str, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in ("summary", "brief", "answer", "draft", "prep", "summary_text", "digest", "text"):
                if key in result:
                    return result[key]
        return json.dumps(result, indent=2, default=str)
