"""Session manager with persistence and context clipping."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from miniopenclaw.core.events import AgentResponse, MediaItem, MessageEvent


class SessionManager:
    """Stores per-conversation history with channel/user/thread isolation."""

    def __init__(
        self,
        storage_path: str | Path = "~/.miniopenclaw/sessions.json",
        max_turns: int = 20,
        max_context_chars: int = 6000,
    ) -> None:
        self._storage_path = Path(storage_path).expanduser()
        self._max_turns = max_turns
        self._max_context_chars = max_context_chars
        self._messages: dict[str, list[MessageEvent]] = {}
        self._load()

    @staticmethod
    def session_key(channel: str, user_id: str, thread_id: str) -> str:
        return f"{channel}:{user_id}:{thread_id}"

    @staticmethod
    def _session_key(event: MessageEvent) -> str:
        return SessionManager.session_key(event.channel, event.user_id, event.thread_id)

    def get_context(self, event: MessageEvent) -> list[MessageEvent]:
        key = self._session_key(event)
        return list(self._messages.get(key, []))

    def get_session_messages(self, channel: str, user_id: str, thread_id: str) -> list[MessageEvent]:
        key = self.session_key(channel, user_id, thread_id)
        return list(self._messages.get(key, []))

    def list_sessions(self) -> list[str]:
        return sorted(self._messages.keys())

    def clear_session(self, channel: str, user_id: str, thread_id: str) -> bool:
        key = self.session_key(channel, user_id, thread_id)
        existed = key in self._messages
        if existed:
            del self._messages[key]
            self._persist()
        return existed

    def save_turn(self, event: MessageEvent, response: AgentResponse) -> None:
        key = self._session_key(event)
        turns = self._messages.setdefault(key, [])
        turns.append(event)
        turns.append(
            MessageEvent(
                channel=event.channel,
                user_id=event.user_id,
                thread_id=event.thread_id,
                content=response.text,
                ts=datetime.now(timezone.utc),
                metadata={"role": "assistant", "status": response.status.value},
            )
        )
        self._messages[key] = self._clip(turns)
        self._persist()

    def _clip(self, turns: list[MessageEvent]) -> list[MessageEvent]:
        """Clip by max turns and by total context characters."""
        limit_by_turns = self._max_turns * 2
        clipped = turns[-limit_by_turns:]

        total_chars = 0
        result: list[MessageEvent] = []
        for item in reversed(clipped):
            total_chars += len(item.content)
            if total_chars > self._max_context_chars:
                break
            result.append(item)
        result.reverse()
        return result

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: [self._dump_event(event) for event in events] for key, events in self._messages.items()}
        self._storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self._storage_path.exists():
            return

        raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        loaded: dict[str, list[MessageEvent]] = {}
        for key, items in raw.items():
            loaded[key] = [self._load_event(item) for item in items]
        self._messages = loaded

    @staticmethod
    def _dump_event(event: MessageEvent) -> dict:
        payload = asdict(event)
        payload["ts"] = event.ts.isoformat()
        return payload

    @staticmethod
    def _load_event(payload: dict) -> MessageEvent:
        media = [MediaItem(**item) for item in payload.get("media", [])]
        ts = datetime.fromisoformat(payload["ts"])
        return MessageEvent(
            channel=payload["channel"],
            user_id=payload["user_id"],
            thread_id=payload.get("thread_id", "default"),
            content=payload.get("content", ""),
            ts=ts,
            media=media,
            metadata=payload.get("metadata", {}),
        )
