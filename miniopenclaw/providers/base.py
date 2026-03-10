"""Provider protocol definitions."""

from __future__ import annotations

from typing import Iterator, Protocol


class BaseProvider(Protocol):
    """Unified provider contract for model backends."""

    def generate(self, prompt: str) -> str:
        """Return one complete response."""

    def stream_generate(self, prompt: str) -> Iterator[str]:
        """Return a streamed response iterator."""
