"""Config loader from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from miniopenclaw.config.schema import Config


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _default_model(provider: str) -> str:
    key = provider.lower()
    if key == "gemini":
        return "gemini-2.5-flash"
    if key == "openai":
        return "gpt-4.1-mini"
    if key == "claude":
        return "claude-3-7-sonnet-latest"
    if key == "ark":
        return "doubao-seed-1-6-flash-250828"
    return "gpt-4.1-mini"


def load_config() -> Config:
    """Load config from environment with sensible provider defaults."""
    # Auto-load project .env so users don't need to run `source .env` manually.
    load_dotenv()
    provider = os.getenv("MINICLAW_PROVIDER", "gemini")

    return Config(
        provider=provider,
        model=os.getenv("MINICLAW_MODEL", _default_model(provider)),
        stream=_to_bool(os.getenv("MINICLAW_STREAM"), False),
        timeout_seconds=_to_float(os.getenv("MINICLAW_TIMEOUT_SECONDS"), 60.0),
        max_retries=_to_int(os.getenv("MINICLAW_MAX_RETRIES"), 2),
        retry_backoff_seconds=_to_float(os.getenv("MINICLAW_RETRY_BACKOFF_SECONDS"), 0.7),
        api_key=os.getenv("MINICLAW_API_KEY", ""),
        api_base_url=os.getenv("MINICLAW_BASE_URL", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        ark_api_key=os.getenv("ARK_API_KEY", os.getenv("VOLCENGINE_API_KEY", "")),
        ark_base_url=os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
    )
