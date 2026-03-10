"""Configuration schema objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Config:
    """Root app configuration."""

    model: str = "gemini-2.5-flash"
    channel_allowlist: list[str] | None = None
