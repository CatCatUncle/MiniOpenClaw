"""Provider protocol definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TypedDict


class ChatMessage(TypedDict):
    """Normalized chat message shape passed to providers."""

    role: str
    content: str


class BaseProvider(ABC):
    """Unified provider contract for model backends."""

    @abstractmethod
    def generate(self, messages: list[ChatMessage], model: str) -> str:
        """Return one complete response text."""

    @abstractmethod
    def stream_generate(self, messages: list[ChatMessage], model: str) -> Iterator[str]:
        """Yield streaming response chunks."""
