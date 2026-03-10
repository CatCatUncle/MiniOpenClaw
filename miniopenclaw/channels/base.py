"""Base channel contract."""

from __future__ import annotations

from typing import Protocol

from miniopenclaw.core.events import AgentResponse, MessageEvent


class BaseChannel(Protocol):
    """Channel adapter lifecycle and send contract."""

    name: str

    async def start(self) -> None:
        """Start receiving events from this channel."""

    async def stop(self) -> None:
        """Stop channel resources."""

    async def send_message(self, event: MessageEvent, response: AgentResponse) -> None:
        """Send a response back to the source thread/user."""
