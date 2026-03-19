"""Terminal REPL interface for NEXUS."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode

console = Console()


class REPLInterface:
    """Terminal-based REPL for user interaction."""

    def __init__(self):
        """Initialize the REPL interface."""
        self.session: Optional[SessionContext] = None
        self.running = False
        self.agent = None

    def set_agent(self, agent) -> None:
        """Attach an agent to the REPL."""
        self.agent = agent

    def start_session(self, session_id: Optional[str] = None, execution_mode: ExecutionMode = ExecutionMode.AUTO, existing_session: Optional[SessionContext] = None) -> SessionContext:
        """Start or resume a session.

        Args:
            session_id: Optional session ID for a new session.
            execution_mode: Initial execution mode.
            existing_session: A previously saved session to resume.

        Returns:
            The active session.
        """
        if existing_session:
            self.session = existing_session
            self.session.set_execution_mode(execution_mode)
        else:
            self.session = SessionContext(session_id=session_id, execution_mode=execution_mode)
        self._print_welcome()
        return self.session

    def _print_welcome(self) -> None:
        """Print welcome message."""
        welcome = """
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║              ⟳ NEXUS - Autonomous Code Assistant         ║
║     Neural Executive Xperiment for Unified Software       ║
║                  automation                               ║
║                                                            ║
║  Version 0.1.0 | Session: [bold cyan]{}[/bold cyan]         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

Type [bold]/help[/bold] for available commands.
Enter your coding task or instruction below:
""".format(self.session.session_id[:8])
        console.print(Markdown(welcome))

    async def run_loop(self) -> None:
        """Run the main REPL loop."""
        if not self.session:
            console.print("[red]Error: No session started[/red]")
            return

        # Initialize MCP tools if the agent has an executor
        if self.agent and hasattr(self.agent.tool_executor, "initialize"):
            console.print("[dim]Initializing tools...[/dim]")
            await self.agent.tool_executor.initialize()

        self.running = True
        try:
            while self.running:
                try:
                    # Get user input
                    user_input = console.input(
                        "\n[bold cyan]→ You:[/bold cyan] "
                    ).strip()

                    if not user_input:
                        continue

                    # Handle commands
                    if user_input.startswith("/"):
                        await self._handle_command(user_input)
                        continue

                    # Process user message through agent
                    if self.agent:
                        result = await self.agent.execute(user_input)
                        if result.success:
                            self.stream_response(result.final_response or result.message)
                        else:
                            self.show_error(result.error or result.message)
                    else:
                        self.session.add_user_message(user_input)
                        console.print("\n[dim][No agent connected][/dim]")

                except KeyboardInterrupt:
                    console.print(
                        "\n[yellow]⚠️  Interrupted. Type /exit to quit.[/yellow]"
                    )

        except EOFError:
            console.print("\n[yellow]Exiting NEXUS...[/yellow]")
            self.running = False

    async def _handle_command(self, command: str) -> None:
        """Handle a command.

        Args:
            command: The command string (starts with /).
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self._show_help()
        elif cmd == "/exit":
            self.running = False
            console.print("[yellow]Exiting NEXUS. Goodbye![/yellow]")
        elif cmd == "/clear":
            self._clear_history()
        elif cmd == "/history":
            self._show_history()
        elif cmd == "/mode":
            self._set_mode(arg)
        elif cmd == "/context":
            self._show_context()
        elif cmd == "/status":
            self._show_status()
        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            console.print("Type [bold]/help[/bold] for available commands.")

    def _show_help(self) -> None:
        """Show help message."""
        help_text = """
# NEXUS Commands

## Execution
- **Type your task** - Give a natural language instruction
- `/exec` - Execute pending changes (if in manual mode)

## Session Management
- `/clear` - Clear conversation history
- `/history` - Show conversation history
- `/context` - Show current context window (messages sent to LLM)
- `/status` - Show session status

## Settings
- `/mode [auto|manual|confirmation]` - Set execution mode
  - `auto` - Auto-execute all tools
  - `manual` - Require confirmation for all tools
  - `confirmation` - Confirm high-risk operations only

## Utility
- `/help` - Show this help message
- `/exit` - Exit NEXUS

## Examples

```
→ You: write a Python script that prints hello world
⟳ NEXUS: I'll create a script for you...

→ You: /mode manual
✅ Execution mode set to: manual

→ You: /history
📋 Showing last 5 messages...
```
"""
        console.print(Markdown(help_text))

    def _clear_history(self) -> None:
        """Clear conversation history."""
        if self.session:
            msg_count = len(self.session.messages)
            self.session.messages = []
            self.session.reset_iteration()
            console.print(
                f"[green]✅ Cleared {msg_count} messages from history[/green]"
            )

    def _show_history(self) -> None:
        """Show conversation history."""
        if not self.session or not self.session.messages:
            console.print("[yellow]📋 No messages in history yet[/yellow]")
            return

        console.print("\n[bold]📋 Conversation History[/bold]")
        console.print(
            f"[dim]Showing last {len(self.session.messages)} messages[/dim]\n"
        )

        for message in self.session.messages[-10:]:  # Show last 10
            if message.role.value == "user":
                console.print(f"[bold cyan]→ You:[/bold cyan] {message.content}")
            elif message.role.value == "assistant":
                console.print(
                    f"[bold green]⟳ NEXUS:[/bold green] {message.content}"
                )
                if message.tool_calls:
                    console.print(
                        f"[dim]  (Using {len(message.tool_calls)} tool(s))[/dim]"
                    )

    def _set_mode(self, mode_str: str) -> None:
        """Set execution mode.

        Args:
            mode_str: The mode (auto, manual, or confirmation).
        """
        if not self.session:
            return

        mode_map = {
            "auto": ExecutionMode.AUTO,
            "manual": ExecutionMode.MANUAL,
            "confirmation": ExecutionMode.CONFIRMATION,
        }

        mode = mode_map.get(mode_str.lower())
        if mode:
            self.session.set_execution_mode(mode)
            console.print(
                f"[green]✅ Execution mode set to: [bold]{mode.value}[/bold][/green]"
            )
        else:
            console.print(
                f"[red]Invalid mode: {mode_str}[/red]"
            )
            console.print("Available modes: auto, manual, confirmation")

    def _show_context(self) -> None:
        """Show current context window."""
        if not self.session:
            return

        context_msgs = self.session.get_context_messages()
        console.print(f"\n[bold]📍 Context Window ({len(context_msgs)} messages)[/bold]\n")

        for msg in context_msgs:
            role_label = "→ You" if msg.role.value == "user" else "⟳ NEXUS"
            color = "cyan" if msg.role.value == "user" else "green"
            console.print(f"[{color}][{role_label}][/{color}]")
            console.print(f"  {msg.content[:100]}...")
            console.print()

    def _show_status(self) -> None:
        """Show session status."""
        if not self.session:
            return

        meta = self.session.metadata
        console.print("\n[bold]⚙️  Session Status[/bold]\n")
        console.print(f"Session ID: [cyan]{meta.session_id}[/cyan]")
        console.print(f"Created: {meta.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"Updated: {meta.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"Mode: [bold]{meta.execution_mode.value}[/bold]")
        console.print(f"LLM: {meta.llm_model}")
        console.print(f"Messages: {len(self.session.messages)}")
        console.print(f"Tool calls: {meta.tool_calls_count}")
        console.print(f"Iterations: {self.session.iteration_count}/{self.session.max_iterations}")
        console.print()

    def stream_response(self, response: str) -> None:
        """Stream a response from the assistant.

        Args:
            response: The response text.
        """
        console.print(f"\n[bold green]⟳ NEXUS:[/bold green] {response}")

    def show_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Show that a tool is being called.

        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.
        """
        args_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
        console.print(f"[dim]🔧 Calling: {tool_name}({args_str})[/dim]")

    def show_tool_result(self, tool_name: str, success: bool, output: str) -> None:
        """Show a tool execution result.

        Args:
            tool_name: Name of the tool.
            success: Whether the tool succeeded.
            output: Tool output.
        """
        status = "✅" if success else "❌"
        console.print(f"{status} {tool_name}: {output[:100]}")

    def prompt_confirmation(self, message: str) -> bool:
        """Prompt for user confirmation.

        Args:
            message: The confirmation prompt.

        Returns:
            True if user confirms, False otherwise.
        """
        response = typer.confirm(f"[yellow]⚠️  {message}[/yellow]", default=False)
        return response

    def show_error(self, error_message: str) -> None:
        """Show an error message.

        Args:
            error_message: The error message.
        """
        console.print(f"[red]❌ Error: {error_message}[/red]")


def create_repl() -> REPLInterface:
    """Create a REPL interface instance."""
    return REPLInterface()
