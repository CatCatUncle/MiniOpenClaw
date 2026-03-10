"""Feishu channel adapter (webhook server + send API)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from typing import Any

import aiohttp
from aiohttp import web

from miniopenclaw.config.schema import Config
from miniopenclaw.core.events import MessageEvent
from miniopenclaw.core.router import AgentRouter


class FeishuChannel:
    """Feishu webhook channel."""

    name = "feishu"

    def __init__(self, router: AgentRouter, config: Config) -> None:
        self._router = router
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._token_cache: tuple[str, float] | None = None

    async def start(self) -> None:
        if not self._config.feishu_app_id or not self._config.feishu_app_secret:
            raise RuntimeError("FEISHU_APP_ID and FEISHU_APP_SECRET are required when MINICLAW_FEISHU_ENABLED=true")

        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        app = web.Application()
        app.router.add_post(self._config.feishu_webhook_path, self._handle_webhook)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            host=self._config.feishu_webhook_host,
            port=self._config.feishu_webhook_port,
        )
        await self._site.start()

        while True:
            await asyncio.sleep(3600)

    async def stop(self) -> None:
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_message(self, event: MessageEvent, response_text: str) -> None:
        session = self._session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        own_session = self._session is None

        receive_id = event.metadata.get("chat_id") or event.metadata.get("open_id")
        receive_id_type = "chat_id" if event.metadata.get("chat_id") else "open_id"
        if not receive_id:
            if own_session:
                await session.close()
            return

        token = await self._get_tenant_access_token(session)
        chunks = _split_text(response_text, self._config.feishu_max_chunk_chars)
        for chunk in chunks:
            payload = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": chunk}, ensure_ascii=False),
            }
            headers = {"Authorization": f"Bearer {token}"}
            url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
            async with session.post(url, json=payload, headers=headers):
                pass

        if own_session:
            await session.close()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        body = await request.json()

        if body.get("type") == "url_verification":
            return web.json_response({"challenge": body.get("challenge")})

        event = body.get("event", {})
        header = body.get("header", {})

        if self._config.feishu_verify_token and header.get("token") != self._config.feishu_verify_token:
            return web.json_response({"code": 0})

        if not _verify_signature(request, self._config.feishu_app_secret):
            return web.json_response({"code": 0})

        if header.get("event_type") != "im.message.receive_v1":
            return web.json_response({"code": 0})

        message = event.get("message", {})
        sender = event.get("sender", {}).get("sender_id", {})
        chat_id = message.get("chat_id")
        open_id = sender.get("open_id")
        user_id = sender.get("user_id") or open_id or ""

        if self._config.feishu_allow_from and user_id not in set(self._config.feishu_allow_from):
            return web.json_response({"code": 0})
        if self._config.feishu_allow_chat_ids and chat_id not in set(self._config.feishu_allow_chat_ids):
            return web.json_response({"code": 0})

        if message.get("message_type") != "text":
            return web.json_response({"code": 0})

        content = json.loads(message.get("content", "{}"))
        text = (content.get("text") or "").strip()
        if not text:
            return web.json_response({"code": 0})

        thread_id = f"feishu:{chat_id or open_id}"
        event_obj = MessageEvent(
            channel="feishu",
            user_id=str(user_id),
            thread_id=thread_id,
            content=text,
            metadata={"chat_id": chat_id, "open_id": open_id},
        )
        response = self._router.handle_incoming(event_obj)
        await self.send_message(event_obj, response.text)
        return web.json_response({"code": 0})

    async def _get_tenant_access_token(self, session: aiohttp.ClientSession) -> str:
        now = time.time()
        if self._token_cache and self._token_cache[1] > now + 60:
            return self._token_cache[0]

        payload = {
            "app_id": self._config.feishu_app_id,
            "app_secret": self._config.feishu_app_secret,
        }
        async with session.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json=payload,
        ) as resp:
            data = await resp.json()

        token = data.get("tenant_access_token", "")
        expire = now + int(data.get("expire", 7200))
        self._token_cache = (token, expire)
        return token


def _verify_signature(request: web.Request, app_secret: str) -> bool:
    """Best-effort verification for Feishu webhook signatures."""
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")
    if not (timestamp and nonce and signature and app_secret):
        return True

    body = request._read_bytes or b""
    content = timestamp + nonce + body.decode("utf-8")
    mac = hmac.new(app_secret.encode("utf-8"), content.encode("utf-8"), hashlib.sha256)
    sign = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(sign, signature)


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + limit])
        start += limit
    return chunks
