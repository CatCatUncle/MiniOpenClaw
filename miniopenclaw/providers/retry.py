"""Retry helpers for provider calls."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from miniopenclaw.providers.errors import ErrorKind, ProviderError

T = TypeVar("T")

RETRYABLE_KINDS = {ErrorKind.NETWORK, ErrorKind.SERVICE, ErrorKind.TIMEOUT, ErrorKind.RATE_LIMIT}


def with_retry(
    fn: Callable[[], T],
    max_retries: int,
    backoff_base_seconds: float,
) -> T:
    """Retry provider operations with exponential backoff."""
    attempt = 0
    while True:
        try:
            return fn()
        except ProviderError as exc:
            if attempt >= max_retries or exc.kind not in RETRYABLE_KINDS:
                raise
            sleep_seconds = backoff_base_seconds * (2**attempt)
            time.sleep(sleep_seconds)
            attempt += 1
