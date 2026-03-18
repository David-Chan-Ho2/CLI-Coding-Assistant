"""NEXUS - Main entry point for the CLI coding assistant."""

import asyncio
import signal
import sys
from typing import Optional

import typer
from rich.console import Console

from nexus.cli.repl import create_repl
from nexus.config.settings import settings
from nexus.core.types import ExecutionMode

console = Console()
app = typer.Typer(
    name="NEXUS",
    help="Autonomous CLI Coding Assistant",
    pretty_exceptions_enable=True,
)


def _handle_signal(signum, frame):
    """Handle signals for graceful shutdown."""
    console.print("\n[yellow]⚠️  Received shutdown signal. Exiting...[/yellow]")
    sys.exit(0)


@app.command()
def main(
    session_id: Optional[str] = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume existing session by ID",
    ),
    mode: str = typer.Option(
        "auto",
        "--mode",
        "-m",
        help="Execution mode: auto, manual, or confirmation",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode",
    ),
) -> None:
    """Start NEXUS - the autonomous CLI coding assistant."""

    # Validate settings
    settings.validate()

    # Setup signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Parse execution mode
    mode_map = {
        "auto": ExecutionMode.AUTO,
        "manual": ExecutionMode.MANUAL,
        "confirmation": ExecutionMode.CONFIRMATION,
    }

    execution_mode = mode_map.get(mode.lower(), ExecutionMode.AUTO)
    if mode.lower() not in mode_map:
        console.print(f"[red]Invalid mode: {mode}[/red]")
        console.print("Available modes: auto, manual, confirmation")
        raise typer.Exit(1)

    # Create and start REPL
    repl = create_repl()
    repl.start_session(session_id=session_id, execution_mode=execution_mode)

    # Run the main loop
    try:
        asyncio.run(repl.run_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Exiting NEXUS.[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        if debug:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
