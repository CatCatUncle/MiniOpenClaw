"""Agent loop contract and a minimal implementation."""

from __future__ import annotations

from typing import Protocol

from miniopenclaw.core.events import AgentResponse, MessageEvent


class AgentLoop(Protocol):
    """Contract for any core agent loop implementation."""

    def run(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        """Execute one turn and return a normalized response."""


class EchoAgentLoop:
    """Minimal loop for early wiring validation."""

    def run(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        del context
        return AgentResponse(text=f"I received: {event.content}")
