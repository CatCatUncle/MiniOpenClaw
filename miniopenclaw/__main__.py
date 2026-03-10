"""Entry point for `python -m miniopenclaw`."""

import sys

from miniopenclaw.cli.commands import app


if __name__ == "__main__":
    # Backward compatibility: if user passes options directly, route to `agent`.
    # Example: `python -m miniopenclaw -m "hello"` -> `python -m miniopenclaw agent -m "hello"`.
    known_subcommands = {"agent", "gateway", "--help", "-h", "--version"}
    if len(sys.argv) >= 2 and sys.argv[1] not in known_subcommands and sys.argv[1].startswith("-"):
        sys.argv.insert(1, "agent")
    app()
