"""Hi-EV tool that exposes the safe code sandbox to the chat/intent layer."""

from __future__ import annotations

from typing import Any

from ev.core import register
from ev.sandbox.runner import CodeRunner

from ev.tools.registry import Tool


@register("tool", "sandbox")
class SandboxTool(Tool):
    """Tier-2 tool that runs a restricted Python snippet in a subprocess sandbox.

    The snippet may read from `input_data`, compute, and assign to `result` to
    return structured output. Because generated code is inherently risky, the
    user must confirm before execution in the HUD/voice interface.
    """

    def __init__(self, timeout: float = 10.0):
        super().__init__(
            name="sandbox",
            tier=2,
            description=(
                "Run a small, restricted Python snippet in a sandbox and return "
                "its result, stdout, and stderr. The code can use a whitelist of "
                "stdlib modules and read from input_data; assign to the variable "
                "result to return structured output."
            ),
        )
        self.runner = CodeRunner(timeout=timeout)

    async def run(
        self,
        code: str,
        inputs: dict[str, Any] | None = None,
        language: str = "python",
    ) -> dict[str, Any]:
        if language.lower() != "python":
            return {"error": "Only Python is supported by the sandbox."}
        if not isinstance(code, str) or not code.strip():
            return {"error": "No code provided."}
        return self.runner.run(code, inputs=inputs or {})
