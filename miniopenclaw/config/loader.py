"""Config loader placeholder."""

from __future__ import annotations

from miniopenclaw.config.schema import Config


def load_config() -> Config:
    """Load config; currently returns defaults."""
    return Config()
