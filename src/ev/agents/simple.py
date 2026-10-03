"""Simple single-turn chat agent."""

from ev.core import BaseAgent, register
from ev.core.component import AgentContext, AgentResult
from ev.llm.client import LLMClient


@register("agent", "simple")
class SimpleAgent(BaseAgent):
    """Direct model passthrough with optional system prompt injection."""

    name = "simple"

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()

    async def run(self, input_text: str, context: AgentContext | None = None) -> AgentResult:
        context = context or AgentContext()
        messages = [
            {"role": "system", "content": self._system_prompt(context)},
            *context.messages,
            {"role": "user", "content": input_text},
        ]
        text = await self.client.complete(messages, temperature=0.7, max_tokens=1024)
        return AgentResult(text=text.strip(), route="fast")

    def _system_prompt(self, context: AgentContext) -> str:
        return (
            "You are EV, a local-first personal AI operating system. You are helpful, concise, "
            "and you only act on the user's personal projects and data. You refuse requests "
            "that touch work accounts, employer data, or any patent/IP-sensitive material."
        )
