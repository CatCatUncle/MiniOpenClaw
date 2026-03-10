"""Provider error types and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorKind(str, Enum):
    """High-level provider error categories."""

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    SERVICE = "service"
    TIMEOUT = "timeout"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class ProviderError(Exception):
    """Normalized provider error used by the agent loop."""

    kind: ErrorKind
    user_message: str
    details: str = ""

    def __str__(self) -> str:
        if self.details:
            return f"{self.user_message} ({self.details})"
        return self.user_message


def classify_exception(exc: Exception) -> ProviderError:
    """Best-effort exception classification across SDKs."""
    text = str(exc).lower()

    if any(token in text for token in ("api key", "unauthorized", "forbidden", "401", "403", "authentication")):
        return ProviderError(ErrorKind.AUTH, "Authentication failed. Check API key and account permissions.", str(exc))

    if any(token in text for token in ("429", "rate", "quota", "too many requests")):
        return ProviderError(ErrorKind.RATE_LIMIT, "Rate limit reached. Retry later or reduce request rate.", str(exc))

    if any(token in text for token in ("timeout", "timed out", "deadline")):
        return ProviderError(ErrorKind.TIMEOUT, "Request timed out. Check network and provider status.", str(exc))

    if any(token in text for token in ("ssl", "connection", "dns", "eof", "network", "could not resolve", "name resolution")):
        return ProviderError(ErrorKind.NETWORK, "Network error while contacting provider.", str(exc))

    if any(token in text for token in ("500", "502", "503", "504", "internal server", "bad gateway", "service unavailable")):
        return ProviderError(ErrorKind.SERVICE, "Provider service is temporarily unavailable.", str(exc))

    return ProviderError(ErrorKind.UNKNOWN, "Unexpected provider error.", str(exc))
