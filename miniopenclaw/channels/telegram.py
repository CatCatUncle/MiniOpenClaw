"""Telegram channel adapter (polling mode)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from miniopenclaw.config.schema import Config
from miniopenclaw.core.events import MessageEvent
from miniopenclaw.core.router import AgentRouter


class TelegramChannel:
    """Telegram long-polling channel."""

    name = "telegram"

    def __init__(self, router: AgentRouter, config: Config) -> None:
        self._router = router
        self._config = config
        self._running = False
        self._offset = 0
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._running = True
        token = self._config.telegram_bot_token
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required when MINICLAW_TELEGRAM_ENABLED=true")

        api_base = f"https://api.telegram.org/bot{token}"
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))

        while self._running:
            try:
                updates = await self._get_updates(api_base)
                for update in updates:
                    await self._handle_update(api_base, update)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(max(self._config.telegram_poll_interval_seconds, 1.0))

        await self.stop()

    async def stop(self) -> None:
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_message(self, event: MessageEvent, response_text: str) -> None:
        token = self._config.telegram_bot_token
        api_base = f"https://api.telegram.org/bot{token}"
        session = self._session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        own_session = self._session is None

        chat_id = event.metadata.get("chat_id")
        message_thread_id = event.metadata.get("message_thread_id")
        chunks = _split_text(response_text, self._config.telegram_max_chunk_chars)
        for chunk in chunks:
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
            }
            if message_thread_id is not None:
                payload["message_thread_id"] = message_thread_id
            async with session.post(f"{api_base}/sendMessage", json=payload):
                pass

        if own_session:
            await session.close()

    async def _get_updates(self, api_base: str) -> list[dict[str, Any]]:
        assert self._session is not None
        payload = {"timeout": 30, "offset": self._offset + 1}
        async with self._session.post(f"{api_base}/getUpdates", json=payload) as resp:
            data = await resp.json()
        items = data.get("result", []) if data.get("ok") else []
        return items

    async def _handle_update(self, api_base: str, update: dict[str, Any]) -> None:
        self._offset = max(self._offset, int(update.get("update_id", 0)))

        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        text = (message.get("text") or "").strip()
        if not text:
            return

        from_user = message.get("from") or {}
        user_id = str(from_user.get("id", ""))
        if self._config.telegram_allow_from and user_id not in set(self._config.telegram_allow_from):
            return

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        chat_type = chat.get("type")
        message_thread_id = message.get("message_thread_id")

        if chat_type == "private":
            thread_id = f"private:{user_id}"
        elif message_thread_id is not None:
            thread_id = f"chat:{chat_id}:thread:{message_thread_id}"
        else:
            thread_id = f"chat:{chat_id}"

        event = MessageEvent(
            channel="telegram",
            user_id=user_id,
            thread_id=thread_id,
            content=text,
            metadata={
                "chat_id": chat_id,
                "chat_type": chat_type,
                "message_thread_id": message_thread_id,
            },
        )
        response = self._router.handle_incoming(event)
        await self.send_message(event, response.text)


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + limit])
        start += limit
    return chunks
