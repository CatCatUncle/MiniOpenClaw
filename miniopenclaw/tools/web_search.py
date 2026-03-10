"""Web search tool supporting Brave and Tavily."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from miniopenclaw.tools.base import ToolError


class WebSearchTool:
    """Search the web with Brave Search or Tavily API."""

    name = "web_search"
    description = "Search the web and return concise results."
    json_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 300},
            "provider": {"type": "string", "enum": ["brave", "tavily"]},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        default_provider: str,
        brave_api_key: str,
        tavily_api_key: str,
        timeout_seconds: float,
    ) -> None:
        self._default_provider = default_provider.lower().strip() or "brave"
        self._brave_api_key = brave_api_key
        self._tavily_api_key = tavily_api_key
        self._timeout_seconds = timeout_seconds

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        provider = str(args.get("provider") or self._default_provider).strip().lower()
        max_results = int(args.get("max_results", 5))

        if not query:
            raise ToolError("web_search requires a non-empty query")
        if max_results < 1 or max_results > 10:
            raise ToolError("max_results must be between 1 and 10")
        if provider not in {"brave", "tavily"}:
            raise ToolError("provider must be one of: brave, tavily")

        if provider == "brave":
            return self._search_brave(query, max_results)
        return self._search_tavily(query, max_results)

    def _search_brave(self, query: str, max_results: int) -> dict[str, Any]:
        if not self._brave_api_key:
            raise ToolError("BRAVE_SEARCH_API_KEY is required when using Brave search")

        qs = urllib.parse.urlencode({"q": query, "count": max_results})
        url = f"https://api.search.brave.com/res/v1/web/search?{qs}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._brave_api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ToolError("Brave search request failed", f"HTTP {exc.code}") from exc
        except Exception as exc:
            raise ToolError("Brave search request failed", str(exc)) from exc

        items = payload.get("web", {}).get("results", [])[:max_results]
        results = []
        for item in items:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                }
            )
        return {
            "provider": "brave",
            "query": query,
            "results": results,
            "summary": self._summarize(results),
        }

    def _search_tavily(self, query: str, max_results: int) -> dict[str, Any]:
        if not self._tavily_api_key:
            raise ToolError("TAVILY_API_KEY is required when using Tavily search")

        url = "https://api.tavily.com/search"
        data = json.dumps(
            {
                "api_key": self._tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ToolError("Tavily search request failed", f"HTTP {exc.code}") from exc
        except Exception as exc:
            raise ToolError("Tavily search request failed", str(exc)) from exc

        items = payload.get("results", [])[:max_results]
        results = []
        for item in items:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
            )
        return {
            "provider": "tavily",
            "query": query,
            "results": results,
            "summary": self._summarize(results),
        }

    @staticmethod
    def _summarize(results: list[dict[str, str]]) -> str:
        if not results:
            return "No search results found."
        lines = []
        for idx, item in enumerate(results, start=1):
            title = item.get("title", "").strip() or "(untitled)"
            url = item.get("url", "").strip()
            snippet = (item.get("snippet", "") or "").strip().replace("\n", " ")
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            lines.append(f"{idx}. {title}\\n   {url}\\n   {snippet}")
        return "\n".join(lines)
