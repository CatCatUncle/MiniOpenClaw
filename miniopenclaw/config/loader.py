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


def _to_list(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    items = [x.strip() for x in value.split(",")]
    return [x for x in items if x]


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
        search_provider=os.getenv("MINICLAW_SEARCH_PROVIDER", "brave"),
        brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        workspace_root=os.getenv("MINICLAW_WORKSPACE_ROOT", "."),
        shell_allow_prefixes=_to_list(
            os.getenv("MINICLAW_SHELL_ALLOW_PREFIXES"),
            ["ls", "cat", "rg", "sed", "head", "tail", "pwd", "echo", "mkdir"],
        ),
        max_agent_steps=_to_int(os.getenv("MINICLAW_MAX_AGENT_STEPS"), 8),
        telegram_enabled=_to_bool(os.getenv("MINICLAW_TELEGRAM_ENABLED"), False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_allow_from=_to_list(os.getenv("TELEGRAM_ALLOW_FROM"), []),
        telegram_poll_interval_seconds=_to_float(os.getenv("TELEGRAM_POLL_INTERVAL_SECONDS"), 1.5),
        telegram_max_chunk_chars=_to_int(os.getenv("TELEGRAM_MAX_CHUNK_CHARS"), 3500),
        feishu_enabled=_to_bool(os.getenv("MINICLAW_FEISHU_ENABLED"), False),
        feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        feishu_verify_token=os.getenv("FEISHU_VERIFY_TOKEN", ""),
        feishu_webhook_host=os.getenv("FEISHU_WEBHOOK_HOST", "127.0.0.1"),
        feishu_webhook_port=_to_int(os.getenv("FEISHU_WEBHOOK_PORT"), 8765),
        feishu_webhook_path=os.getenv("FEISHU_WEBHOOK_PATH", "/feishu/webhook"),
        feishu_allow_from=_to_list(os.getenv("FEISHU_ALLOW_FROM"), []),
        feishu_allow_chat_ids=_to_list(os.getenv("FEISHU_ALLOW_CHAT_IDS"), []),
        feishu_max_chunk_chars=_to_int(os.getenv("FEISHU_MAX_CHUNK_CHARS"), 1800),
    )
