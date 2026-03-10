"""Routes channel events through session context and agent loop."""

from __future__ import annotations

from miniopenclaw.core.agent_loop import AgentLoop
from miniopenclaw.core.events import AgentResponse, MessageEvent
from miniopenclaw.session.manager import SessionManager


class AgentRouter:
    """Single entry point from channels/CLI into the core pipeline."""

    def __init__(self, agent_loop: AgentLoop, session_manager: SessionManager) -> None:
        self._agent_loop = agent_loop
        self._sessions = session_manager

    def handle_incoming(self, event: MessageEvent) -> AgentResponse:
        """Unified flow: inbound event -> context -> agent -> persist -> outbound."""
        context = self._sessions.get_context(event)
        response = self._agent_loop.run(event=event, context=context)
        self._sessions.save_turn(event=event, response=response)
        return response
