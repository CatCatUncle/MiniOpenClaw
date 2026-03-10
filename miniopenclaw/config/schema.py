"""Configuration schema objects."""

from __future__ import annotations

from dataclasses import dataclass


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

    channel_allowlist: list[str] | None = None
