"""Tool schema helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolSpec:
    """Serializable tool specification."""

    name: str
    description: str
    json_schema: dict[str, Any]
