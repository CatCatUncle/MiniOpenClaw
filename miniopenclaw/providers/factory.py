"""Provider factory based on runtime config."""

from __future__ import annotations

from miniopenclaw.config.schema import Config
from miniopenclaw.providers.anthropic_provider import AnthropicProvider
from miniopenclaw.providers.base import BaseProvider
from miniopenclaw.providers.errors import ProviderError, ErrorKind
from miniopenclaw.providers.gemini_provider import GeminiProvider
from miniopenclaw.providers.openai_compat_provider import OpenAICompatProvider


def create_provider(config: Config) -> BaseProvider:
    """Create provider instance from config provider type."""
    provider = config.provider.lower()

    if provider == "gemini":
        return GeminiProvider(
            api_key=config.gemini_api_key,
            base_url=config.gemini_base_url,
            max_retries=config.max_retries,
            backoff_base_seconds=config.retry_backoff_seconds,
        )

    if provider == "openai":
        return OpenAICompatProvider(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            backoff_base_seconds=config.retry_backoff_seconds,
        )

    if provider == "claude":
        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            base_url=config.anthropic_base_url,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            backoff_base_seconds=config.retry_backoff_seconds,
        )

    if provider == "ark":
        return OpenAICompatProvider(
            api_key=config.ark_api_key,
            base_url=config.ark_base_url,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            backoff_base_seconds=config.retry_backoff_seconds,
        )

    if provider == "openai_compat":
        return OpenAICompatProvider(
            api_key=config.api_key,
            base_url=config.api_base_url,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            backoff_base_seconds=config.retry_backoff_seconds,
        )

    raise ProviderError(ErrorKind.CONFIG, f"Unsupported provider: {config.provider}")
