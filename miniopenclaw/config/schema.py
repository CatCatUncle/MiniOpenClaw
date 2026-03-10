"""Configuration schema objects."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Config:
    """Root app configuration."""

    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    stream: bool = False

    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.7

    api_key: str = ""
    api_base_url: str = ""

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"

    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    search_provider: str = "brave"
    brave_search_api_key: str = ""
    tavily_api_key: str = ""

    workspace_root: str = "."
    shell_allow_prefixes: list[str] = field(default_factory=lambda: ["ls", "cat", "rg", "sed", "head", "tail", "pwd", "echo", "mkdir"])
    max_agent_steps: int = 8

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_allow_from: list[str] = field(default_factory=list)
    telegram_poll_interval_seconds: float = 1.5
    telegram_max_chunk_chars: int = 3500

    feishu_enabled: bool = False
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verify_token: str = ""
    feishu_webhook_host: str = "127.0.0.1"
    feishu_webhook_port: int = 8765
    feishu_webhook_path: str = "/feishu/webhook"
    feishu_allow_from: list[str] = field(default_factory=list)
    feishu_allow_chat_ids: list[str] = field(default_factory=list)
    feishu_max_chunk_chars: int = 1800

    channel_allowlist: list[str] | None = None
