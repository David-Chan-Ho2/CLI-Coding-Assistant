"""NEXUS - Main entry point for the CLI coding assistant."""

import asyncio
import signal
import sys
from typing import Optional

import typer
from rich.console import Console

from nexus.cli.repl import create_repl
from nexus.config.settings import settings
from nexus.core.agent import Agent
from nexus.core.types import ExecutionMode
from nexus.mcp.client import MCPClientManager
from nexus.mcp.servers.filesystem import filesystem_server
from nexus.mcp.servers.search import search_server
from nexus.persistence.store import SessionStore
from nexus.tools.executor import MCPToolExecutor

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

    # Create LLM provider (Groq if key available, else Ollama)
    if settings.GROQ_API_KEY:
        from nexus.llm.groq_provider import GroqProvider
        llm_provider = GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
        )
    else:
        from nexus.llm.ollama_provider import OllamaProvider
        llm_provider = OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
        )
        console.print("[yellow]No GROQ_API_KEY found — using Ollama (tool calling not supported).[/yellow]")

    # Set up MCP tool layer
    mcp_manager = MCPClientManager()
    mcp_manager.register_server("filesystem", filesystem_server)
    mcp_manager.register_server("search", search_server)
    tool_executor = MCPToolExecutor(mcp_manager)

    # Load or create session
    store = SessionStore()
    existing_session = None
    if session_id and store.exists(session_id):
        try:
            existing_session = store.load(session_id)
            console.print(f"[green]Resuming session {session_id[:8]}...[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not load session: {e}. Starting fresh.[/yellow]")

    # Create and start REPL
    repl = create_repl()
    session = repl.start_session(
        session_id=session_id,
        execution_mode=execution_mode,
        existing_session=existing_session,
    )

    # Create agent and attach to REPL
    agent = Agent(
        llm_provider=llm_provider,
        session=session,
        tool_executor=tool_executor,
    )
    repl.set_agent(agent)

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
    finally:
        if repl.session:
            store.save(repl.session)
            console.print(f"[dim]Session saved ({repl.session.session_id[:8]}). Resume with --session {repl.session.session_id}[/dim]")


if __name__ == "__main__":
    app()
