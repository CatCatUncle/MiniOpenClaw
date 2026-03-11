"""Typer CLI for MiniOpenClaw."""

from __future__ import annotations

import asyncio
import atexit
import os
import sys
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from miniopenclaw.channels import ChannelManager
from miniopenclaw.config.loader import load_config
from miniopenclaw.core.events import AgentResponse, MessageEvent
from miniopenclaw.core.router import AgentRouter
from miniopenclaw.providers.errors import ProviderError
from miniopenclaw.runtime import build_runtime
from miniopenclaw.session.manager import SessionManager
from miniopenclaw.skills import SkillLoader
from miniopenclaw.tools import ToolExecutor

AGENT_HEADER = "🦞 miniOpenClaw"
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

app = typer.Typer(
    name="miniopenclaw",
    help="MiniOpenClaw - a compact, extensible personal AI agent.",
    no_args_is_help=True,
)
console = Console()


class TerminalState:
    """Preserves and restores terminal settings to avoid input corruption."""

    def __init__(self) -> None:
        self._saved = None

    def save(self) -> None:
        try:
            if not os.isatty(sys.stdin.fileno()):
                return
            import termios

            self._saved = termios.tcgetattr(sys.stdin.fileno())
        except Exception:
            self._saved = None

    def restore(self) -> None:
        if self._saved is None:
            return
        try:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved)
        except Exception:
            pass


def _history_path() -> Path:
    path = Path("~/.miniopenclaw/cli_history.txt").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _make_prompt_session() -> PromptSession:
    return PromptSession(
        history=FileHistory(str(_history_path())),
        multiline=False,
        enable_open_in_editor=False,
    )


def _render_response(response: AgentResponse, show_logs: bool = False) -> None:
    console.print(AGENT_HEADER)
    if response.chunks:
        text = "".join(response.chunks)
    else:
        text = response.text or ""
    console.print(f"  {text.replace(chr(10), chr(10) + '  ')}")
    if show_logs:
        console.print("[dim]--- logs ---[/dim]")
        console.print(f"[dim]status={response.status.value}[/dim]")
        if response.tool_calls:
            for idx, call in enumerate(response.tool_calls, start=1):
                if call.error:
                    console.print(
                        f"[dim]tool[{idx}] name={call.name} outcome=error args={call.args} error={call.error}[/dim]"
                    )
                else:
                    result = (call.result or "").replace("\n", " ")
                    if len(result) > 200:
                        result = result[:197] + "..."
                    console.print(
                        f"[dim]tool[{idx}] name={call.name} outcome=ok args={call.args} result={result}[/dim]"
                    )
        else:
            console.print("[dim]tool_calls=0[/dim]")
        if response.metadata:
            console.print(f"[dim]metadata={response.metadata}[/dim]")


def _build_router(
    session_store: str,
    max_turns: int,
    max_context_chars: int,
    provider: str | None,
    model: str | None,
    stream: bool | None,
) -> tuple[AgentRouter, SessionManager, ToolExecutor]:
    cfg = load_config()
    if provider:
        cfg.provider = provider
    if model:
        cfg.model = model
    if stream is not None:
        cfg.stream = stream

    return build_runtime(cfg, session_store=session_store, max_turns=max_turns, max_context_chars=max_context_chars)


def _handle_slash_command(
    text: str,
    tool_executor: ToolExecutor,
    session_manager: SessionManager,
    skill_loader: SkillLoader | None,
    pending_confirmation: dict[str, object],
    channel: str,
    user_id: str,
    thread_id: str,
) -> tuple[bool, str]:
    """Handle slash commands. Returns (handled, maybe_new_thread_id)."""
    if not text.startswith("/"):
        return False, thread_id

    parts = text.split()
    command = parts[0].lower()

    if command == "/clear":
        cleared = session_manager.clear_session(channel, user_id, thread_id)
        console.print("Cleared current session." if cleared else "Current session is already empty.")
        return True, thread_id

    if command == "/history":
        limit = 10
        if len(parts) >= 2 and parts[1].isdigit():
            limit = max(1, int(parts[1]))
        messages = session_manager.get_session_messages(channel, user_id, thread_id)
        if not messages:
            console.print("No history in current session.")
            return True, thread_id
        console.print(f"History ({min(limit, len(messages))}/{len(messages)}):")
        for item in messages[-limit:]:
            role = item.metadata.get("role", "user")
            console.print(f"  [{role}] {item.content}")
        return True, thread_id

    if command == "/session":
        if len(parts) >= 2:
            new_thread = parts[1]
            console.print(f"Switched session thread: {thread_id} -> {new_thread}")
            return True, new_thread
        key = SessionManager.session_key(channel, user_id, thread_id)
        console.print(f"Current session: {key}")
        sessions = session_manager.list_sessions()
        if sessions:
            console.print("Known sessions:")
            for item in sessions[-10:]:
                console.print(f"  {item}")
        else:
            console.print("No saved sessions yet.")
        return True, thread_id

    if command == "/web":
        if len(parts) < 2:
            console.print("Usage: /web <query> OR /web <brave|tavily> <query>")
            return True, thread_id

        provider_override = None
        query_parts = parts[1:]
        if parts[1].lower() in {"brave", "tavily"}:
            provider_override = parts[1].lower()
            query_parts = parts[2:]
        query = " ".join(query_parts).strip()
        if not query:
            console.print("Usage: /web <query> OR /web <brave|tavily> <query>")
            return True, thread_id

        tool_args = {"query": query, "max_results": 5}
        if provider_override:
            tool_args["provider"] = provider_override
        tool_call = tool_executor.execute("web_search", tool_args)
        if tool_call.error:
            console.print(f"[red]Web search failed:[/red] {tool_call.error}")
        else:
            console.print("🔎 websearch")
            console.print(f"  {tool_call.result.replace(chr(10), chr(10) + '  ')}")
        return True, thread_id

    if command == "/findskill":
        if len(parts) < 2:
            console.print("Usage: /findskill <query> OR /findskill <query> || <task>")
            return True, thread_id
        payload = text[len("/findskill") :].strip()
        if "||" in payload:
            query, task = [x.strip() for x in payload.split("||", 1)]
        else:
            query, task = payload, payload
        call = tool_executor.execute("find_skill", {"query": query, "task": task})
        if call.error:
            console.print(f"[red]find_skill failed:[/red] {call.error}")
        else:
            console.print("🧩 find_skill")
            console.print(f"  {call.result.replace(chr(10), chr(10) + '  ')}")
        return True, thread_id

    if command == "/read":
        if len(parts) < 2:
            console.print("Usage: /read <path>")
            return True, thread_id
        call = tool_executor.execute("read_file", {"path": parts[1]})
        if call.error:
            console.print(f"[red]Read failed:[/red] {call.error}")
        else:
            console.print("🧰 read_file")
            console.print(f"  {call.result.replace(chr(10), chr(10) + '  ')}")
        return True, thread_id

    if command == "/write":
        if len(parts) < 3:
            console.print("Usage: /write <path> <content>")
            return True, thread_id
        path = parts[1]
        content = text.split(None, 2)[2]
        call = tool_executor.execute("write_file", {"path": path, "content": content})
        if call.error and call.error.startswith("CONFIRM_REQUIRED:"):
            pending_confirmation["tool"] = "write_file"
            pending_confirmation["args"] = {"path": path, "content": content}
            console.print(f"[yellow]{call.error}[/yellow]")
            console.print("Run /confirm to proceed.")
            return True, thread_id
        if call.error:
            console.print(f"[red]Write failed:[/red] {call.error}")
        else:
            console.print("🧰 write_file")
            console.print(f"  {call.result.replace(chr(10), chr(10) + '  ')}")
        return True, thread_id

    if command == "/shell":
        if len(parts) < 2:
            console.print("Usage: /shell <command>")
            return True, thread_id
        shell_command = text.split(None, 1)[1]
        call = tool_executor.execute("shell", {"command": shell_command})
        if call.error and call.error.startswith("CONFIRM_REQUIRED:"):
            pending_confirmation["tool"] = "shell"
            pending_confirmation["args"] = {"command": shell_command}
            console.print(f"[yellow]{call.error}[/yellow]")
            console.print("Run /confirm to proceed.")
            return True, thread_id
        if call.error:
            console.print(f"[red]Shell failed:[/red] {call.error}")
        else:
            console.print("🧰 shell")
            console.print(f"  {call.result.replace(chr(10), chr(10) + '  ')}")
        return True, thread_id

    if command == "/confirm":
        tool = pending_confirmation.get("tool")
        args = pending_confirmation.get("args")
        if not tool or not isinstance(args, dict):
            console.print("No pending high-risk action to confirm.")
            return True, thread_id
        args = dict(args)
        args["confirm"] = True
        call = tool_executor.execute(str(tool), args)
        pending_confirmation.clear()
        if call.error:
            console.print(f"[red]Confirmed action failed:[/red] {call.error}")
        else:
            console.print("🧰 confirmed")
            console.print(f"  {call.result.replace(chr(10), chr(10) + '  ')}")
        return True, thread_id

    if command == "/skills":
        if skill_loader is None:
            console.print("Skill system is disabled. Set MINICLAW_SKILL_ENABLED=true.")
            return True, thread_id

        if len(parts) == 1 or parts[1].lower() == "list":
            names = skill_loader.list_skills()
            console.print(f"Skills ({len(names)}):")
            if not names:
                console.print("  (none)")
            else:
                for name in names:
                    console.print(f"  - {name}")
            return True, thread_id

        action = parts[1].lower()
        if action == "refresh":
            trace = skill_loader.refresh()
            console.print(f"Skills refreshed: {trace.get('skill_count', 0)} loaded")
            return True, thread_id

        if action == "match":
            query = text.split(None, 2)[2].strip() if len(parts) >= 3 else ""
            if not query:
                console.print("Usage: /skills match <text>")
                return True, thread_id
            selected, trace = skill_loader.resolve_for_text(query)
            console.print(f"Matched ({len(selected)}): {[s.name for s in selected]}")
            console.print(f"Trace: {trace}")
            return True, thread_id

        if action == "show":
            if len(parts) < 3:
                console.print("Usage: /skills show <skill_name>")
                return True, thread_id
            target = parts[2].lower()
            skill = skill_loader.get_skill(target)
            if not skill:
                console.print(f"Skill not found: {target}")
                return True, thread_id
            console.print(f"Skill: {skill.name}")
            console.print(f"Path: {skill.path}")
            console.print(f"Description: {skill.description or '(empty)'}")
            return True, thread_id

        if action == "create":
            if len(parts) < 3:
                console.print("Usage: /skills create <name> [description]")
                return True, thread_id
            name = parts[2]
            description = text.split(None, 3)[3].strip() if len(parts) >= 4 else ""
            if name.lower() in {"new-skill", "my-new-skill", "skill", "test-skill"}:
                suggestions = skill_loader.suggest_names(description or name)
                console.print(
                    "Name is too generic. Suggested names:\n"
                    + "\n".join([f"  - {x}" for x in suggestions])
                )
                console.print(f"Use: /skills create {suggestions[0]} {description}".rstrip())
                return True, thread_id
            result = skill_loader.create_skill(name=name, description=description)
            if not result.get("ok"):
                console.print(f"[red]Create failed:[/red] {result.get('error', 'unknown error')}")
                return True, thread_id
            console.print(f"Skill created: {result['name']}")
            console.print(f"Path: {result['path']}")
            return True, thread_id

        if action == "suggest":
            purpose = text.split(None, 2)[2].strip() if len(parts) >= 3 else ""
            if not purpose:
                console.print("Usage: /skills suggest <purpose>")
                return True, thread_id
            suggestions = skill_loader.suggest_names(purpose)
            console.print("Suggested names:")
            for item in suggestions:
                console.print(f"  - {item}")
            console.print(f"Create with: /skills create {suggestions[0]} {purpose}")
            return True, thread_id

        console.print("Usage: /skills [list|refresh|match <text>|show <name>|suggest <purpose>|create <name> [description]]")
        return True, thread_id

    if command in {"/help", "/?"}:
        console.print(
            "Slash commands: /help, /clear, /history [n], /session [thread_id], "
            "/web [provider] <query>, /findskill <query> [|| task], /read <path>, /write <path> <content>, /shell <cmd>, "
            "/confirm, /skills [list|refresh|match <text>|show <name>|suggest <purpose>|create <name> [description]], /exit"
        )
        return True, thread_id

    console.print(f"Unknown command: {command}. Try /help.")
    return True, thread_id


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="One-shot input message"),
    channel: str = typer.Option("cli", "--channel", help="Inbound channel name"),
    user_id: str = typer.Option("local-user", "--user-id", help="User id in the source channel"),
    thread_id: str = typer.Option("default", "--thread-id", help="Thread/session identifier"),
    provider: str = typer.Option(None, "--provider", help="Provider: gemini/openai/claude/ark/openai_compat"),
    model: str = typer.Option(None, "--model", help="Model name for the selected provider"),
    stream: bool | None = typer.Option(None, "--stream/--no-stream", help="Enable/disable streaming responses"),
    session_store: str = typer.Option(
        "~/.miniopenclaw/sessions.json",
        "--session-store",
        help="Path to session persistence file",
    ),
    max_turns: int = typer.Option(20, "--max-turns", help="Max turns kept per session"),
    max_context_chars: int = typer.Option(6000, "--max-context-chars", help="Max chars kept in context"),
    logs: bool = typer.Option(False, "--logs", help="Show tool-calling and runtime logs"),
) -> None:
    """Run one-shot or interactive chat through the core router."""
    try:
        router, session_manager, tool_executor = _build_router(
            session_store,
            max_turns,
            max_context_chars,
            provider,
            model,
            stream,
        )
    except ProviderError as exc:
        console.print(f"[red]Provider config error:[/red] {exc.user_message}")
        raise typer.Exit(1)

    if message:
        event = MessageEvent(channel=channel, user_id=user_id, thread_id=thread_id, content=message)
        response = router.handle_incoming(event)
        _render_response(response, show_logs=logs)
        return

    terminal = TerminalState()
    terminal.save()
    atexit.register(terminal.restore)
    prompt = _make_prompt_session()
    current_thread_id = thread_id
    pending_confirmation: dict[str, object] = {}
    skill_loader: SkillLoader | None = None
    cfg = load_config()
    if cfg.skill_enabled:
        skill_loader = SkillLoader(
            search_paths=cfg.skill_paths,
            max_skills=cfg.skill_max_loaded,
            script_timeout_seconds=cfg.skill_script_timeout_seconds,
        )

    console.print("Interactive mode (type /help, /exit to quit)")
    while True:
        try:
            with patch_stdout():
                text = prompt.prompt("You: ")
        except (KeyboardInterrupt, EOFError):
            console.print("\nGoodbye!")
            break

        cleaned = text.strip()
        if not cleaned:
            continue
        if cleaned.lower() in EXIT_COMMANDS:
            console.print("Goodbye!")
            break

        handled, current_thread_id = _handle_slash_command(
            cleaned,
            tool_executor=tool_executor,
            session_manager=session_manager,
            skill_loader=skill_loader,
            pending_confirmation=pending_confirmation,
            channel=channel,
            user_id=user_id,
            thread_id=current_thread_id,
        )
        if handled:
            continue

        event = MessageEvent(
            channel=channel,
            user_id=user_id,
            thread_id=current_thread_id,
            content=cleaned,
        )
        response = router.handle_incoming(event)
        _render_response(response, show_logs=logs)


@app.command()
def gateway(
    provider: str = typer.Option(None, "--provider", help="Provider: gemini/openai/claude/ark/openai_compat"),
    model: str = typer.Option(None, "--model", help="Model name for enabled channels"),
    stream: bool | None = typer.Option(None, "--stream/--no-stream", help="Enable/disable streaming responses"),
    session_store: str = typer.Option(
        "~/.miniopenclaw/sessions.json",
        "--session-store",
        help="Path to session persistence file",
    ),
    max_turns: int = typer.Option(20, "--max-turns", help="Max turns kept per session"),
    max_context_chars: int = typer.Option(6000, "--max-context-chars", help="Max chars kept in context"),
) -> None:
    """Run all enabled channels concurrently (Telegram/Feishu)."""
    cfg = load_config()
    if provider:
        cfg.provider = provider
    if model:
        cfg.model = model
    if stream is not None:
        cfg.stream = stream

    try:
        router, _, _ = build_runtime(
            cfg,
            session_store=session_store,
            max_turns=max_turns,
            max_context_chars=max_context_chars,
        )
        manager = ChannelManager(router=router, config=cfg)
        console.print("Starting gateway channels...")
        asyncio.run(manager.run_forever())
    except ProviderError as exc:
        console.print(f"[red]Provider config error:[/red] {exc.user_message}")
        raise typer.Exit(1)
    except RuntimeError as exc:
        console.print(f"[red]Gateway error:[/red] {exc}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
