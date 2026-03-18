"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode


@pytest.fixture
def session_context():
    """Create a test session context."""
    return SessionContext(execution_mode=ExecutionMode.AUTO)


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    from nexus.llm.provider import LLMProvider

    provider = AsyncMock(spec=LLMProvider)
    provider.invoke = AsyncMock(
        return_value={
            "content": "Test response",
            "tool_calls": [],
            "stop_reason": "end_turn",
        }
    )
    return provider


@pytest.fixture
def mock_mcp_client_manager():
    """Create a mock MCP client manager."""
    manager = MagicMock()
    manager.execute_tool = AsyncMock(
        return_value={"success": True, "output": "Tool executed"}
    )
    return manager


@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry."""
    registry = MagicMock()
    registry.get_tools = MagicMock(
        return_value=[
            {
                "name": "write_file",
                "description": "Write a file",
                "parameters": {"type": "object"},
            }
        ]
    )
    return registry


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
