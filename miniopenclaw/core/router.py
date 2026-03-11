"""Routes channel events through session context and agent loop."""

from __future__ import annotations

from miniopenclaw.core.agent_loop import AgentLoop
from miniopenclaw.core.events import AgentResponse, MessageEvent
from miniopenclaw.memory import MemoryStore
from miniopenclaw.session.manager import SessionManager


class AgentRouter:
    """Single entry point from channels/CLI into the core pipeline."""

    def __init__(
        self,
        agent_loop: AgentLoop,
        session_manager: SessionManager,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._agent_loop = agent_loop
        self._sessions = session_manager
        self._memory_store = memory_store

    def handle_incoming(self, event: MessageEvent) -> AgentResponse:
        """Unified flow: inbound event -> context -> agent -> persist -> outbound."""
        context = self._sessions.get_context(event)
        response = self._agent_loop.run(event=event, context=context)
        self._sessions.save_turn(event=event, response=response)
        if self._memory_store is not None:
            memory_trace = self._memory_store.remember(event=event, response=response)
            response.metadata["memory_store"] = memory_trace
        return response
