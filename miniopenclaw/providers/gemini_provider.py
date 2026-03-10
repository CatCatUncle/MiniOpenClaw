"""Gemini provider via google-genai SDK."""

from __future__ import annotations

from collections.abc import Iterator

from miniopenclaw.providers.base import BaseProvider, ChatMessage
from miniopenclaw.providers.errors import ProviderError, ErrorKind, classify_exception
from miniopenclaw.providers.retry import with_retry


class GeminiProvider(BaseProvider):
    """Gemini provider with custom base URL support."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        max_retries: int,
        backoff_base_seconds: float,
    ) -> None:
        if not api_key:
            raise ProviderError(ErrorKind.CONFIG, "GEMINI_API_KEY is required for provider=gemini.")

        try:
            from google import genai
        except ModuleNotFoundError as exc:
            raise ProviderError(ErrorKind.CONFIG, "Missing dependency: google-genai") from exc

        self._client = genai.Client(api_key=api_key, http_options={"base_url": base_url})
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def generate(self, messages: list[ChatMessage], model: str) -> str:
        def call() -> str:
            try:
                response = self._client.models.generate_content(model=model, contents=self._to_gemini_contents(messages))
                return response.text or ""
            except ProviderError:
                raise
            except Exception as exc:
                raise classify_exception(exc) from exc

        return with_retry(call, self._max_retries, self._backoff_base_seconds)

    def stream_generate(self, messages: list[ChatMessage], model: str) -> Iterator[str]:
        def build_stream():
            try:
                return self._client.models.generate_content_stream(model=model, contents=self._to_gemini_contents(messages))
            except ProviderError:
                raise
            except Exception as exc:
                raise classify_exception(exc) from exc

        stream = with_retry(build_stream, self._max_retries, self._backoff_base_seconds)
        for chunk in stream:
            text = chunk.text or ""
            if text:
                yield text

    @staticmethod
    def _to_gemini_contents(messages: list[ChatMessage]) -> list[dict]:
        contents: list[dict] = []
        for item in messages:
            role = item["role"]
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": item["content"]}]})
        return contents
