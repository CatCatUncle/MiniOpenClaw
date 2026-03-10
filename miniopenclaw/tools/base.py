"""Tool contracts and common tool errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolError(Exception):
    """Normalized tool error."""

    message: str
    details: str = ""

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message


class Tool(Protocol):
    """Tool protocol used by registry and executor."""

    name: str
    description: str
    json_schema: dict[str, Any]

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run tool and return structured result."""
