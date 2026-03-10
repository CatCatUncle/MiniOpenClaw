"""Shared protocol objects across CLI/channels/core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    """Lifecycle status for a single agent response."""

    RUNNING = "running"  # 正在处理
    COMPLETED = "completed"  # 正常完成
    ERROR = "error"  # 处理失败


@dataclass(slots=True)
class MediaItem:
    """Normalized media payload from any channel."""

    kind: str  # 媒体类型，例如 image / file / audio / video
    url: str | None = None  # 远程资源地址（可选）
    file_path: str | None = None  # 本地文件路径（可选）
    mime_type: str | None = None  # MIME 类型，例如 image/png
    metadata: dict[str, Any] = field(default_factory=dict)  # 渠道特有媒体信息


@dataclass(slots=True)
class MessageEvent:
    """Unified inbound message event consumed by the core router."""

    channel: str  # 消息来源渠道，例如 cli / telegram / feishu
    user_id: str  # 发送者在该渠道内的唯一标识
    content: str  # 文本消息正文
    thread_id: str = "default"  # 会话/线程标识，用于区分同一用户的不同上下文
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # 消息时间戳（UTC）
    media: list[MediaItem] = field(default_factory=list)  # 附件列表（图片、文件、音频等）
    metadata: dict[str, Any] = field(default_factory=dict)  # 渠道扩展字段（原始事件ID、群ID等）


@dataclass(slots=True)
class ToolCall:
    """Represents one tool invocation requested or executed by the agent."""

    name: str  # 工具名称
    args: dict[str, Any] = field(default_factory=dict)  # 工具入参
    result: str | None = None  # 执行结果摘要
    error: str | None = None  # 执行错误信息（失败时）


@dataclass(slots=True)
class AgentResponse:
    """Unified outbound response returned by core and rendered by channels."""

    text: str = ""  # 最终文本回复
    status: AgentStatus = AgentStatus.COMPLETED  # 本轮处理状态
    chunks: list[str] = field(default_factory=list)  # 流式分片内容
    tool_calls: list[ToolCall] = field(default_factory=list)  # 本轮涉及的工具调用记录
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外返回信息（耗时、trace_id等）
