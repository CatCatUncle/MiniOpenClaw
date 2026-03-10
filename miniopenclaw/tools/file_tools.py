"""File tools: read_file and write_file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from miniopenclaw.tools.base import ToolError
from miniopenclaw.tools.safety import resolve_workspace_path


class ReadFileTool:
    """Read UTF-8 text file from workspace sandbox."""

    name = "read_file"
    description = "Read a UTF-8 text file from workspace."
    json_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 500},
            "max_chars": {"type": "integer", "minimum": 1, "maximum": 20000},
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = workspace_root

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        path = str(args["path"])
        max_chars = int(args.get("max_chars", 8000))
        resolved = resolve_workspace_path(path, self._workspace_root)
        if not resolved.exists():
            raise ToolError("File not found", details=str(resolved))
        if not resolved.is_file():
            raise ToolError("Path is not a file", details=str(resolved))

        text = resolved.read_text(encoding="utf-8")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        return {
            "path": str(resolved),
            "content": text,
            "summary": f"Read file: {resolved}\n{text}",
        }


class WriteFileTool:
    """Write UTF-8 text file under workspace sandbox."""

    name = "write_file"
    description = "Write UTF-8 text to a file in workspace."
    json_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 500},
            "content": {"type": "string", "minLength": 0, "maxLength": 200000},
            "confirm": {"type": "boolean"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = workspace_root

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        path = str(args["path"])
        content = str(args["content"])
        confirm = bool(args.get("confirm", False))

        resolved = resolve_workspace_path(path, self._workspace_root)
        if resolved.exists() and not confirm:
            raise ToolError(
                "CONFIRM_REQUIRED: write_file would overwrite existing file",
                details=str(resolved),
            )

        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "path": str(resolved),
            "bytes": len(content.encode("utf-8")),
            "summary": f"Wrote file: {resolved} ({len(content)} chars)",
        }


class AppendFileTool:
    """Append UTF-8 text to file under workspace sandbox."""

    name = "append_file"
    description = "Append UTF-8 text to a file in workspace."
    json_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 500},
            "content": {"type": "string", "minLength": 0, "maxLength": 200000},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = workspace_root

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        path = str(args["path"])
        content = str(args["content"])
        resolved = resolve_workspace_path(path, self._workspace_root)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("a", encoding="utf-8") as f:
            f.write(content)
        return {
            "path": str(resolved),
            "bytes_appended": len(content.encode("utf-8")),
            "summary": f"Appended to file: {resolved} ({len(content)} chars)",
        }
