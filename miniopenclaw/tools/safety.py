"""Safety helpers for file and shell tools."""

from __future__ import annotations

from pathlib import Path

from miniopenclaw.tools.base import ToolError

DANGEROUS_SHELL_TOKENS = {
    "rm -rf",
    "rm -fr",
    "mkfs",
    "dd if=",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "git reset --hard",
    "git checkout --",
    ":(){:|:&};:",
}


def resolve_workspace_path(path_str: str, workspace_root: str) -> Path:
    """Resolve path and enforce workspace sandbox boundaries."""
    root = Path(workspace_root).expanduser().resolve()
    target = Path(path_str).expanduser()
    if not target.is_absolute():
        target = (root / target).resolve()
    else:
        target = target.resolve()

    if target != root and root not in target.parents:
        raise ToolError("Path is outside workspace sandbox", details=f"workspace={root}, target={target}")
    return target


def ensure_not_dangerous_shell(command: str) -> None:
    lower = command.lower()
    for token in DANGEROUS_SHELL_TOKENS:
        if token in lower:
            raise ToolError(
                "CONFIRM_REQUIRED: blocked dangerous shell command",
                details=f"matched token: {token}",
            )


def ensure_allowed_shell_prefix(command: str, allow_prefixes: list[str]) -> None:
    stripped = command.strip()
    if not stripped:
        raise ToolError("shell command is empty")
    if not allow_prefixes:
        return
    if any(stripped.startswith(prefix) for prefix in allow_prefixes):
        return
    raise ToolError(
        "Shell command is not in allowlist",
        details=f"allowed prefixes: {', '.join(allow_prefixes)}",
    )
