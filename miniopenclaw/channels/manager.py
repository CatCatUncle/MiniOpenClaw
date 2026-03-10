"""Channel manager for concurrent channel runtime."""

from __future__ import annotations

import asyncio

from miniopenclaw.channels.feishu import FeishuChannel
from miniopenclaw.channels.telegram import TelegramChannel
from miniopenclaw.config.schema import Config
from miniopenclaw.core.router import AgentRouter


class ChannelManager:
    """Start and supervise enabled channels concurrently."""

    def __init__(self, router: AgentRouter, config: Config) -> None:
        self._channels = []
        if config.telegram_enabled:
            self._channels.append(TelegramChannel(router=router, config=config))
        if config.feishu_enabled:
            self._channels.append(FeishuChannel(router=router, config=config))

    async def run_forever(self) -> None:
        if not self._channels:
            raise RuntimeError("No channels enabled. Set MINICLAW_TELEGRAM_ENABLED or MINICLAW_FEISHU_ENABLED.")

        tasks = [asyncio.create_task(channel.start(), name=f"channel:{channel.name}") for channel in self._channels]
        try:
            await asyncio.gather(*tasks)
        finally:
            for channel in self._channels:
                await channel.stop()
            for task in tasks:
                if not task.done():
                    task.cancel()
