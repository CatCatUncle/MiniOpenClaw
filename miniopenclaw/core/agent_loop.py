"""Agent loop contract and provider-backed implementation."""

from __future__ import annotations

import re
from typing import Protocol

from miniopenclaw.core.events import AgentResponse, AgentStatus, MessageEvent
from miniopenclaw.providers.base import BaseProvider, ChatMessage
from miniopenclaw.providers.errors import ProviderError


class AgentLoop(Protocol):
    """Contract for any core agent loop implementation."""

    def run(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        """Execute one turn and return a normalized response."""


class ProviderAgentLoop:
    """Run turns by delegating to the configured provider."""

    def __init__(self, provider: BaseProvider, model: str, stream: bool = False) -> None:
        self._provider = provider
        self._model = model
        self._stream = stream

    def run(self, event: MessageEvent, context: list[MessageEvent]) -> AgentResponse:
        messages = self._build_messages(context=context, event=event)
        try:
            if self._stream:
                chunks = list(self._provider.stream_generate(messages=messages, model=self._model))
                text = "".join(chunks)
                return AgentResponse(text=text, chunks=chunks)

            text = self._provider.generate(messages=messages, model=self._model)
            return AgentResponse(text=text)
        except ProviderError as exc:
            return AgentResponse(
                text=f"Error [{exc.kind.value}]: {exc.user_message}",
                status=AgentStatus.ERROR,
                metadata={"error_kind": exc.kind.value, "error_details": exc.details},
            )

    @staticmethod
    def _build_messages(context: list[MessageEvent], event: MessageEvent) -> list[ChatMessage]:
        messages: list[ChatMessage] = [
            {
                "role": "system",
                "content": (
                    "Respond in the same language as the user's latest message by default. "
                    "Only switch language when the user explicitly asks for it."
                ),
            }
        ]
        for item in context:
            role = item.metadata.get("role", "user")
            if role not in {"system", "user", "assistant"}:
                role = "user"
            messages.append({"role": role, "content": item.content})

        # Add an explicit language hint for providers that are less consistent.
        messages.append(
            {
                "role": "system",
                "content": f"Preferred response language: {ProviderAgentLoop._detect_language(event.content)}.",
            }
        )
        messages.append({"role": "user", "content": event.content})
        return messages

    @staticmethod
    def _detect_language(text: str) -> str:
        """Rough language hint based on Unicode ranges in latest user input."""
        if re.search(r"[\u4e00-\u9fff]", text):
            return "Chinese"
        if re.search(r"[\u3040-\u30ff]", text):
            return "Japanese"
        if re.search(r"[\uac00-\ud7af]", text):
            return "Korean"
        return "English"
