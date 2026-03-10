"""Anthropic provider for Claude models."""

from __future__ import annotations

from collections.abc import Iterator

from miniopenclaw.providers.base import BaseProvider, ChatMessage
from miniopenclaw.providers.errors import ProviderError, ErrorKind, classify_exception
from miniopenclaw.providers.retry import with_retry


class AnthropicProvider(BaseProvider):
    """Native Anthropic provider."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        backoff_base_seconds: float,
    ) -> None:
        if not api_key:
            raise ProviderError(ErrorKind.CONFIG, "ANTHROPIC_API_KEY is required for provider=claude.")

        try:
            import anthropic
        except ModuleNotFoundError as exc:
            raise ProviderError(ErrorKind.CONFIG, "Missing dependency: anthropic") from exc

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def generate(self, messages: list[ChatMessage], model: str) -> str:
        system_prompt, chat_messages = self._split_system_prompt(messages)

        def call() -> str:
            try:
                response = self._client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=chat_messages,
                )
                parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
                return "".join(parts)
            except ProviderError:
                raise
            except Exception as exc:
                raise classify_exception(exc) from exc

        return with_retry(call, self._max_retries, self._backoff_base_seconds)

    def stream_generate(self, messages: list[ChatMessage], model: str) -> Iterator[str]:
        # Keep implementation simple and compatible: fallback to one-shot text.
        yield self.generate(messages, model)

    @staticmethod
    def _split_system_prompt(messages: list[ChatMessage]) -> tuple[str, list[dict[str, str]]]:
        system_lines: list[str] = []
        chat_messages: list[dict[str, str]] = []
        for item in messages:
            role = item["role"]
            content = item["content"]
            if role == "system":
                system_lines.append(content)
            else:
                mapped_role = "assistant" if role == "assistant" else "user"
                chat_messages.append({"role": mapped_role, "content": content})
        return "\n".join(system_lines), chat_messages
