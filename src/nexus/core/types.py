"""Core data types and enums for NEXUS."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class ExecutionMode(str, Enum):
    """Execution mode for tool execution."""

    AUTO = "auto"  # Auto-execute all tools
    MANUAL = "manual"  # Require confirmation for all tools
    CONFIRMATION = "confirmation"  # Confirm high-risk tools only


class ErrorCategory(str, Enum):
    """Error categorization for retry logic."""

    TRANSIENT = "transient"  # Retry with backoff
    RATE_LIMIT = "rate_limit"  # Specific backoff strategy
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # Provider down
    TOOL_EXECUTION_ERROR = "tool_error"  # Tool failed
    VALIDATION_ERROR = "validation"  # Don't retry
    USER_INTERRUPTION = "interrupted"  # User cancelled
    UNKNOWN = "unknown"  # Unknown error


class MessageRole(str, Enum):
    """Role of message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class RiskLevel(str, Enum):
    """Risk level for tools."""

    LOW = "low"  # Safe to auto-execute
    MEDIUM = "medium"  # Warn before executing
    HIGH = "high"  # Always require confirmation


@dataclass
class ToolCall:
    """A tool call made by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.MEDIUM


@dataclass
class ToolResult:
    """Result from tool execution."""

    tool_call_id: str
    tool_name: str
    output: str
    success: bool
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class Message:
    """A message in conversation history."""

    id: str
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of agent execution."""

    success: bool
    message: str
    iterations: int = 0
    tool_calls_made: int = 0
    final_response: Optional[str] = None
    error: Optional[str] = None
    error_category: Optional[ErrorCategory] = None


@dataclass
class SessionMetadata:
    """Metadata about a session."""

    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    llm_model: str = "groq"
    total_tokens: int = 0
    tool_calls_count: int = 0
    status: str = "active"  # active, completed, interrupted, error
