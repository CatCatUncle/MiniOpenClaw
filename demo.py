import os

import typer
from prompt_toolkit import prompt as pt_prompt
from rich.console import Console

API_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://api.aicodemirror.com/api/gemini")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
AGENT_HEADER = "🦞 miniOpenClaw"

app = typer.Typer(
    help="A tiny AI-agent-like CLI demo",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def gemini_reply(text: str, model: str = DEFAULT_MODEL, stream: bool = True) -> str:
    """Call Gemini via AICodeMirror base URL."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    try:
        from google import genai
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: google-genai. Install with `uv sync`.") from exc

    client = genai.Client(
        api_key=api_key,
        http_options={"base_url": API_BASE_URL},
    )
    console.print(AGENT_HEADER)
    if stream:
        chunks = client.models.generate_content_stream(
            model=model,
            contents=text,
        )
        console.print("  ", end="")
        full_text = []
        for chunk in chunks:
            text_piece = chunk.text or ""
            if text_piece:
                console.print(text_piece.replace("\n", "\n  "), end="")
                full_text.append(text_piece)
        console.print()
        return "".join(full_text)

    response = client.models.generate_content(
        model=model,
        contents=text,
    )
    reply = response.text or ""
    console.print(f"  {reply.replace(chr(10), chr(10) + '  ')}")
    return reply


def read_user_input() -> str:
    """Read user input with robust line editing; fallback to built-in input."""
    try:
        return pt_prompt("You: ")
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        return input("You: ")


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Send one message and exit"),
    logs: bool = typer.Option(False, "--logs", help="Show internal logs"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Gemini model name"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming output"),
) -> None:
    """Run the demo agent in one-shot or interactive mode."""
    if message:
        if logs:
            console.print("[dim]processing single message...[/dim]")
        try:
            gemini_reply(message, model=model, stream=not no_stream)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        return

    console.print("Interactive mode (type 'exit' to quit)")
    while True:
        try:
            user_text = read_user_input()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye!")
            break

        cleaned = user_text.strip()
        if not cleaned:
            continue

        if cleaned.lower() in {"exit", "quit"}:
            console.print("Goodbye!")
            break

        if logs:
            console.print("[dim]thinking...[/dim]")

        try:
            gemini_reply(cleaned, model=model, stream=not no_stream)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")


if __name__ == "__main__":
    app()
