"""Long-term memory store with lightweight retrieval and safety guards."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from miniopenclaw.core.events import AgentResponse, MessageEvent

_TOKEN_RE = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff]{2,32}")
_SUSPICIOUS_RE = re.compile(
    r"(ignore\s+previous|system\s+prompt|api[_-]?key|secret|<tool_call>|password)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class MemoryEntry:
    """One persisted memory unit."""

    id: str
    session_key: str
    summary: str
    tags: list[str]
    created_at: str
    updated_at: str


class MemoryStore:
    """JSON-backed long-term memory with tagging, retrieval, and compression."""

    def __init__(
        self,
        storage_path: str | Path = "~/.miniopenclaw/memory.json",
        max_items: int = 400,
        retrieve_k: int = 4,
        summary_max_chars: int = 360,
    ) -> None:
        self._storage_path = Path(storage_path).expanduser()
        self._max_items = max_items
        self._retrieve_k = retrieve_k
        self._summary_max_chars = summary_max_chars
        self._entries: list[MemoryEntry] = []
        self._load()

    @staticmethod
    def session_key(event: MessageEvent) -> str:
        return f"{event.channel}:{event.user_id}:{event.thread_id}"

    def retrieve(self, session_key: str, query: str, k: int | None = None) -> tuple[list[MemoryEntry], dict]:
        """Retrieve relevant memory entries for prompt augmentation."""
        take = max(1, k or self._retrieve_k)
        q_tokens = self._tokenize(query)
        ranked: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries:
            score = 0.0
            if entry.session_key == session_key:
                score += 1.0
            e_tokens = set(self._tokenize(entry.summary)) | set(entry.tags)
            overlap = len(q_tokens & e_tokens)
            score += overlap * 0.8
            if score > 0:
                ranked.append((score, entry))

        ranked.sort(key=lambda x: x[0], reverse=True)
        items = [e for _, e in ranked[:take]]
        trace = {
            "query_tokens": sorted(q_tokens)[:12],
            "candidate_count": len(ranked),
            "retrieved_count": len(items),
            "session_key": session_key,
        }
        return items, trace

    def remember(self, event: MessageEvent, response: AgentResponse) -> dict:
        """Persist one conversational memory entry after response generation."""
        session_key = self.session_key(event)
        user = event.content.strip()
        assistant = (response.text or "").strip()
        summary = self._summarize(user=user, assistant=assistant)
        if not summary:
            return {"stored": False, "reason": "empty_summary"}
        if self._is_polluted(summary):
            return {"stored": False, "reason": "pollution_guard"}

        tags = self._extract_tags(user + "\n" + assistant)
        now = datetime.now(timezone.utc).isoformat()
        merged = self._merge_if_possible(session_key=session_key, summary=summary, tags=tags, now=now)
        if not merged:
            self._entries.append(
                MemoryEntry(
                    id=str(uuid.uuid4()),
                    session_key=session_key,
                    summary=summary,
                    tags=tags,
                    created_at=now,
                    updated_at=now,
                )
            )
        self._compress()
        self._persist()
        return {"stored": True, "merged": merged, "tag_count": len(tags)}

    def render_context(self, entries: list[MemoryEntry]) -> str:
        """Render retrieved memory entries into compact prompt context."""
        if not entries:
            return ""
        lines = ["Long-term memory hints (for continuity):"]
        for idx, item in enumerate(entries, start=1):
            tags = ", ".join(item.tags[:6]) if item.tags else "-"
            lines.append(f"{idx}. summary={item.summary}")
            lines.append(f"   tags={tags}")
        return "\n".join(lines)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {x.lower() for x in _TOKEN_RE.findall(text)}

    def _extract_tags(self, text: str) -> list[str]:
        base = sorted(self._tokenize(text), key=len, reverse=True)
        tags: list[str] = []
        for token in base:
            if len(tags) >= 8:
                break
            if token not in tags:
                tags.append(token)
        return tags

    def _summarize(self, user: str, assistant: str) -> str:
        user = re.sub(r"\s+", " ", user).strip()
        assistant = re.sub(r"\s+", " ", assistant).strip()
        if not user and not assistant:
            return ""
        raw = f"用户: {user}; 助手: {assistant}"
        if len(raw) > self._summary_max_chars:
            raw = raw[: self._summary_max_chars - 3] + "..."
        return raw

    @staticmethod
    def _is_polluted(text: str) -> bool:
        if len(text) < 6:
            return True
        if _SUSPICIOUS_RE.search(text):
            return True
        return False

    def _merge_if_possible(self, session_key: str, summary: str, tags: list[str], now: str) -> bool:
        # Merge nearby same-session memories with overlapping tags to avoid memory explosion.
        for idx in range(len(self._entries) - 1, -1, -1):
            item = self._entries[idx]
            if item.session_key != session_key:
                continue
            overlap = set(item.tags) & set(tags)
            if not overlap:
                continue
            merged_summary = f"{item.summary} | {summary}"
            if len(merged_summary) > self._summary_max_chars:
                merged_summary = merged_summary[: self._summary_max_chars - 3] + "..."
            merged_tags = sorted(set(item.tags + tags))[:10]
            self._entries[idx] = MemoryEntry(
                id=item.id,
                session_key=item.session_key,
                summary=merged_summary,
                tags=merged_tags,
                created_at=item.created_at,
                updated_at=now,
            )
            return True
        return False

    def _compress(self) -> None:
        if len(self._entries) <= self._max_items:
            return
        self._entries.sort(key=lambda x: x.updated_at, reverse=True)
        self._entries = self._entries[: self._max_items]

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(item) for item in self._entries]
        self._storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception:
            self._entries = []
            return
        entries: list[MemoryEntry] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                try:
                    entries.append(MemoryEntry(**item))
                except TypeError:
                    continue
        self._entries = entries
