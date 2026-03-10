"""Tool registry and default tool setup."""

from __future__ import annotations

from miniopenclaw.config.schema import Config
from miniopenclaw.tools.base import Tool
from miniopenclaw.tools.file_tools import AppendFileTool, ReadFileTool, WriteFileTool
from miniopenclaw.tools.shell_tool import ShellTool
from miniopenclaw.tools.web_search import WebSearchTool


class ToolRegistry:
    """Simple in-memory tool registry."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())


def build_default_registry(config: Config) -> ToolRegistry:
    """Register default tools based on current configuration."""
    registry = ToolRegistry()
    registry.register(ReadFileTool(workspace_root=config.workspace_root))
    registry.register(WriteFileTool(workspace_root=config.workspace_root))
    registry.register(AppendFileTool(workspace_root=config.workspace_root))
    registry.register(
        ShellTool(
            workspace_root=config.workspace_root,
            allow_prefixes=config.shell_allow_prefixes,
        )
    )
    registry.register(
        WebSearchTool(
            default_provider=config.search_provider,
            brave_api_key=config.brave_search_api_key,
            tavily_api_key=config.tavily_api_key,
            timeout_seconds=config.timeout_seconds,
        )
    )
    return registry
