"""Shell execution tool with allowlist and safety guards."""

from __future__ import annotations

import subprocess
from typing import Any

from miniopenclaw.tools.base import ToolError
from miniopenclaw.tools.safety import ensure_allowed_shell_prefix, ensure_not_dangerous_shell


class ShellTool:
    """Execute shell commands with policy checks."""

    name = "shell"
    description = "Run shell command with allowlist and safety checks."
    json_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "minLength": 1, "maxLength": 1000},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 60},
            "confirm": {"type": "boolean"},
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def __init__(self, workspace_root: str, allow_prefixes: list[str]) -> None:
        self._workspace_root = workspace_root
        self._allow_prefixes = allow_prefixes

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        command = str(args["command"])
        timeout_seconds = int(args.get("timeout_seconds", 12))
        confirm = bool(args.get("confirm", False))

        ensure_allowed_shell_prefix(command, self._allow_prefixes)
        try:
            ensure_not_dangerous_shell(command)
        except ToolError:
            if not confirm:
                raise

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self._workspace_root,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError("Shell command timed out", details=str(exc)) from exc

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        summary_lines = [f"$ {command}", f"exit_code={proc.returncode}"]
        if stdout:
            summary_lines.append(f"stdout:\n{stdout[:4000]}")
        if stderr:
            summary_lines.append(f"stderr:\n{stderr[:4000]}")

        return {
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "summary": "\n".join(summary_lines),
        }
