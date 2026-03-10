"""Typer CLI for MiniOpenClaw."""

from __future__ import annotations

import typer
from rich.console import Console

from miniopenclaw.core.agent_loop import EchoAgentLoop
from miniopenclaw.core.events import MessageEvent
from miniopenclaw.core.router import AgentRouter
from miniopenclaw.session.manager import SessionManager

app = typer.Typer(
    name="miniopenclaw",
    help="MiniOpenClaw - a compact, extensible personal AI agent.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def agent(
    message: str = typer.Option(..., "--message", "-m", help="One-shot input message"),
    channel: str = typer.Option("cli", "--channel", help="Inbound channel name"),
    user_id: str = typer.Option("local-user", "--user-id", help="User id in the source channel"),
    thread_id: str = typer.Option("default", "--thread-id", help="Thread/session identifier"),
) -> None:
    """Run one normalized turn through router and agent loop."""
    router = AgentRouter(agent_loop=EchoAgentLoop(), session_manager=SessionManager())
    event = MessageEvent(
        channel=channel,
        user_id=user_id,
        thread_id=thread_id,
        content=message,
    )
    response = router.handle_incoming(event)
    console.print("🦞 miniOpenClaw")
    console.print(f"  {response.text}")


if __name__ == "__main__":
    app()
