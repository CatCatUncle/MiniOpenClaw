"""In-memory session manager for normalized message events."""

from __future__ import annotations

from collections import defaultdict

from miniopenclaw.core.events import AgentResponse, MessageEvent


class SessionManager:
    """Stores per-conversation history with channel/user/thread isolation."""

    def __init__(self, max_turns: int = 20) -> None:
        self._max_turns = max_turns
        self._messages: dict[str, list[MessageEvent]] = defaultdict(list)

    @staticmethod
    def _session_key(event: MessageEvent) -> str:
        return f"{event.channel}:{event.user_id}:{event.thread_id}"

    def get_context(self, event: MessageEvent) -> list[MessageEvent]:
        key = self._session_key(event)
        return list(self._messages[key])

    def save_turn(self, event: MessageEvent, response: AgentResponse) -> None:
        del response
        key = self._session_key(event)
        self._messages[key].append(event)
        if len(self._messages[key]) > self._max_turns:
            self._messages[key] = self._messages[key][-self._max_turns :]
