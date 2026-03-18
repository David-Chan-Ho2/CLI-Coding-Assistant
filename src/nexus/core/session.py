"""Session management for NEXUS."""

import uuid
from datetime import datetime
from typing import Optional

from .types import ExecutionMode, Message, MessageRole, SessionMetadata, ToolCall, ToolResult


class SessionContext:
    """Manages session state and conversation history."""

    def __init__(self, session_id: Optional[str] = None, execution_mode: ExecutionMode = ExecutionMode.AUTO):
        """Initialize a session context.

        Args:
            session_id: Optional session ID. If None, generates a new one.
            execution_mode: Initial execution mode.
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.metadata = SessionMetadata(
            session_id=self.session_id,
            execution_mode=execution_mode,
        )
        self.messages: list[Message] = []
        self.iteration_count = 0
        self.max_iterations = 10
        self.max_context_messages = 20  # Sliding window

    def add_user_message(self, content: str) -> Message:
        """Add a user message to history.

        Args:
            content: The user's message.

        Returns:
            The created message.
        """
        message = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=content,
        )
        self.messages.append(message)
        self._update_metadata()
        return message

    def add_assistant_message(self, content: str, tool_calls: Optional[list[ToolCall]] = None) -> Message:
        """Add an assistant message to history.

        Args:
            content: The assistant's response.
            tool_calls: Optional list of tool calls made.

        Returns:
            The created message.
        """
        message = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
        )
        self.messages.append(message)
        self._update_metadata()
        return message

    def add_tool_result(self, tool_call_id: str, result: ToolResult) -> None:
        """Add a tool result to the last assistant message.

        Args:
            tool_call_id: ID of the tool call.
            result: The tool execution result.
        """
        # Find the assistant message with this tool call
        for message in reversed(self.messages):
            if message.role == MessageRole.ASSISTANT:
                for call in message.tool_calls:
                    if call.id == tool_call_id:
                        message.tool_results.append(result)
                        self.metadata.tool_calls_count += 1
                        return

    def get_context_messages(self) -> list[Message]:
        """Get messages within context window.

        Returns:
            Last N messages for LLM context.
        """
        return self.messages[-self.max_context_messages :]

    def get_system_prompt(self) -> str:
        """Get the system prompt for the LLM.

        Returns:
            System prompt explaining NEXUS behavior.
        """
        return """You are NEXUS, an autonomous CLI coding assistant. Your role is to:

1. Understand the user's natural language instruction
2. Reason about what tools and actions are needed
3. Make decisions about file operations, searches, and code modifications
4. Return clear, concise responses

Available tools will be provided. Use them autonomously to complete tasks. For each action:
- Think step by step
- Call tools when needed
- Continue until the task is complete or you need user input

Always prioritize:
- Safety (ask for confirmation before destructive operations)
- Clarity (explain what you're doing)
- Completeness (finish the task or explain why you can't)"""

    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Set the execution mode.

        Args:
            mode: The new execution mode.
        """
        self.metadata.execution_mode = mode
        self._update_metadata()

    def should_confirm_tool(self, tool_name: str, risk_level: str) -> bool:
        """Check if a tool needs confirmation.

        Args:
            tool_name: Name of the tool.
            risk_level: Risk level of the tool.

        Returns:
            True if confirmation is needed.
        """
        if self.metadata.execution_mode == ExecutionMode.AUTO:
            return False
        if self.metadata.execution_mode == ExecutionMode.MANUAL:
            return True
        # CONFIRMATION mode: check risk level
        return risk_level == "high"

    def increment_iteration(self) -> None:
        """Increment the iteration counter."""
        self.iteration_count += 1
        self._update_metadata()

    def reset_iteration(self) -> None:
        """Reset iteration counter."""
        self.iteration_count = 0

    def reached_max_iterations(self) -> bool:
        """Check if max iterations reached.

        Returns:
            True if max iterations exceeded.
        """
        return self.iteration_count >= self.max_iterations

    def to_dict(self) -> dict:
        """Serialize session to dictionary.

        Returns:
            Dictionary representation of session.
        """
        return {
            "session_id": self.session_id,
            "metadata": {
                "session_id": self.metadata.session_id,
                "created_at": self.metadata.created_at.isoformat(),
                "updated_at": self.metadata.updated_at.isoformat(),
                "execution_mode": self.metadata.execution_mode.value,
                "llm_model": self.metadata.llm_model,
                "total_tokens": self.metadata.total_tokens,
                "tool_calls_count": self.metadata.tool_calls_count,
                "status": self.metadata.status,
            },
            "messages": [
                {
                    "id": m.id,
                    "role": m.role.value,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.name,
                            "arguments": tc.arguments,
                            "risk_level": tc.risk_level.value,
                        }
                        for tc in m.tool_calls
                    ],
                    "tool_results": [
                        {
                            "tool_call_id": tr.tool_call_id,
                            "tool_name": tr.tool_name,
                            "output": tr.output,
                            "success": tr.success,
                            "error": tr.error,
                            "execution_time_ms": tr.execution_time_ms,
                        }
                        for tr in m.tool_results
                    ],
                }
                for m in self.messages
            ],
            "iteration_count": self.iteration_count,
        }

    def _update_metadata(self) -> None:
        """Update metadata timestamp."""
        self.metadata.updated_at = datetime.now()
