"""OpenAI-compatible provider (OpenAI/OpenRouter/vLLM/ARK)."""

from __future__ import annotations

from collections.abc import Iterator

from miniopenclaw.providers.base import BaseProvider, ChatMessage
from miniopenclaw.providers.errors import ProviderError, ErrorKind, classify_exception
from miniopenclaw.providers.retry import with_retry


class OpenAICompatProvider(BaseProvider):
    """Provider built on the OpenAI Python SDK with custom base_url."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        backoff_base_seconds: float,
    ) -> None:
        if not api_key:
            raise ProviderError(ErrorKind.CONFIG, "API key is required for OpenAI-compatible provider.")

        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise ProviderError(ErrorKind.CONFIG, "Missing dependency: openai") from exc

        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def generate(self, messages: list[ChatMessage], model: str) -> str:
        def call() -> str:
            try:
                response = self._client.chat.completions.create(model=model, messages=messages, stream=False)
                return response.choices[0].message.content or ""
            except ProviderError:
                raise
            except Exception as exc:
                raise classify_exception(exc) from exc

        return with_retry(call, self._max_retries, self._backoff_base_seconds)

    def stream_generate(self, messages: list[ChatMessage], model: str) -> Iterator[str]:
        def call_stream():
            try:
                return self._client.chat.completions.create(model=model, messages=messages, stream=True)
            except ProviderError:
                raise
            except Exception as exc:
                raise classify_exception(exc) from exc

        stream = with_retry(call_stream, self._max_retries, self._backoff_base_seconds)
        for chunk in stream:
            try:
                text = chunk.choices[0].delta.content or ""
            except Exception:
                text = ""
            if text:
                yield text
