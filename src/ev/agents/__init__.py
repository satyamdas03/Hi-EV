"""Hi-EV agent implementations.

Agents are pluggable reasoning loops that take a user input and an
`AgentContext`, then return a structured `AgentResult`. They register via the
global plugin registry (`ev.core.registry`) so the daemon can pick the right
agent for a given route without hard-coded imports.
"""

from ev.agents.orchestrator import OrchestratorAgent
from ev.agents.simple import SimpleAgent

__all__ = ["OrchestratorAgent", "SimpleAgent"]
