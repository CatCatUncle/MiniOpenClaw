"""Shared protocol objects across CLI/channels/core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    """Lifecycle status for a single agent response."""

    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass(slots=True)
class MediaItem:
    """Normalized media payload from any channel."""

    kind: str
    url: str | None = None
    file_path: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessageEvent:
    """Unified inbound message event consumed by the core router."""

    channel: str
    user_id: str
    content: str
    thread_id: str = "default"
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    media: list[MediaItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolCall:
    """Represents one tool invocation requested or executed by the agent."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    error: str | None = None


@dataclass(slots=True)
class AgentResponse:
    """Unified outbound response returned by core and rendered by channels."""

    text: str = ""
    status: AgentStatus = AgentStatus.COMPLETED
    chunks: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
