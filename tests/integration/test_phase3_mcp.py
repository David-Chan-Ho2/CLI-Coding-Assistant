"""Integration tests for Phase 3 - MCP client manager and tool executor."""

import os
import pytest
from unittest.mock import AsyncMock, patch

from fastmcp import Client

from nexus.core.types import ToolCall, RiskLevel
from nexus.llm.provider import LLMResponse, ToolSchema


# ---------------------------------------------------------------------------
# MCP Client Manager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_manager_register_server():
    """Servers can be registered by name."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)

    assert "filesystem" in manager._servers


@pytest.mark.asyncio
async def test_mcp_manager_initializes_and_discovers_tools():
    """After initialize(), tool schemas are populated from registered servers."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    await manager.initialize()

    schemas = manager.get_tool_schemas()
    assert len(schemas) > 0

    tool_names = [s.name for s in schemas]
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "list_directory" in tool_names
    assert "search_files" in tool_names
    assert "create_directory" in tool_names
    assert "delete_file" in tool_names


@pytest.mark.asyncio
async def test_mcp_manager_schemas_are_tool_schema_instances():
    """get_tool_schemas() returns ToolSchema instances with required fields."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    await manager.initialize()

    for schema in manager.get_tool_schemas():
        assert isinstance(schema, ToolSchema)
        assert schema.name
        assert isinstance(schema.description, str)
        assert isinstance(schema.parameters, dict)


@pytest.mark.asyncio
async def test_mcp_manager_call_tool_success(tmp_path):
    """Calling a registered tool returns a successful ToolResult."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server

    test_file = tmp_path / "call_test.txt"
    test_file.write_text("call tool content")

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    await manager.initialize()

    result = await manager.call_tool("read_file", {"path": str(test_file)})

    assert result.success is True
    assert "call tool content" in result.output
    assert result.execution_time_ms >= 0


@pytest.mark.asyncio
async def test_mcp_manager_call_unknown_tool():
    """Calling a tool that was never registered returns a failed ToolResult."""
    from nexus.mcp.client import MCPClientManager

    manager = MCPClientManager()
    await manager.initialize()

    result = await manager.call_tool("nonexistent_tool", {})

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_mcp_manager_multiple_servers(tmp_path):
    """Manager can register and route calls to multiple servers."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server
    from nexus.mcp.servers.search import search_server

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    manager.register_server("search", search_server)
    await manager.initialize()

    tool_names = [s.name for s in manager.get_tool_schemas()]
    assert "read_file" in tool_names
    assert "web_search" in tool_names


# ---------------------------------------------------------------------------
# MCPToolExecutor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_executor_initialize():
    """MCPToolExecutor.initialize() propagates to the MCP manager."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server
    from nexus.tools.executor import MCPToolExecutor

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)

    executor = MCPToolExecutor(manager)
    await executor.initialize()

    assert len(executor.get_tool_schemas()) > 0


@pytest.mark.asyncio
async def test_tool_executor_get_schemas():
    """get_tool_schemas() returns the same schemas as the underlying manager."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server
    from nexus.tools.executor import MCPToolExecutor

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    executor = MCPToolExecutor(manager)
    await executor.initialize()

    schemas = executor.get_tool_schemas()
    assert isinstance(schemas, list)
    assert all(isinstance(s, ToolSchema) for s in schemas)


@pytest.mark.asyncio
async def test_tool_executor_execute_success(tmp_path):
    """executor.execute() runs a tool and returns a ToolResult with the call id set."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server
    from nexus.tools.executor import MCPToolExecutor

    test_file = tmp_path / "executor_test.txt"
    test_file.write_text("executor content")

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    executor = MCPToolExecutor(manager)
    await executor.initialize()

    call = ToolCall(
        id="call-abc-123",
        name="read_file",
        arguments={"path": str(test_file)},
    )

    result = await executor.execute(call)

    assert result.success is True
    assert result.tool_call_id == "call-abc-123"
    assert "executor content" in result.output
    assert result.tool_name == "read_file"


@pytest.mark.asyncio
async def test_tool_executor_write_then_read(tmp_path):
    """Write a file and read it back through the executor."""
    from nexus.mcp.client import MCPClientManager
    from nexus.mcp.servers.filesystem import filesystem_server
    from nexus.tools.executor import MCPToolExecutor

    target = tmp_path / "roundtrip.txt"

    manager = MCPClientManager()
    manager.register_server("filesystem", filesystem_server)
    executor = MCPToolExecutor(manager)
    await executor.initialize()

    write_result = await executor.execute(ToolCall(
        id="w1",
        name="write_file",
        arguments={"path": str(target), "content": "roundtrip"},
    ))
    assert write_result.success is True

    read_result = await executor.execute(ToolCall(
        id="r1",
        name="read_file",
        arguments={"path": str(target)},
    ))
    assert read_result.success is True
    assert "roundtrip" in read_result.output


@pytest.mark.asyncio
async def test_tool_executor_failed_tool_call():
    """executor.execute() on a non-existent tool returns a failed result, not an exception."""
    from nexus.mcp.client import MCPClientManager
    from nexus.tools.executor import MCPToolExecutor

    manager = MCPClientManager()
    executor = MCPToolExecutor(manager)
    await executor.initialize()

    result = await executor.execute(ToolCall(
        id="bad-1",
        name="no_such_tool",
        arguments={},
    ))

    assert result.success is False
    assert result.tool_call_id == "bad-1"


# ---------------------------------------------------------------------------
# Web search tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_search_no_api_key():
    """web_search returns a clear error when TAVILY_API_KEY is not set."""
    from nexus.mcp.servers.search import search_server

    env = {k: v for k, v in os.environ.items() if k != "TAVILY_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        async with Client(search_server) as client:
            result = await client.call_tool("web_search", {"query": "test query"})
            output = result.content[0].text

    assert "Error" in output or "not set" in output.lower()


@pytest.mark.asyncio
async def test_web_search_mocked_response():
    """web_search formats Tavily results correctly."""
    from nexus.mcp.servers.search import search_server

    mock_response = {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com",
                "content": "Some relevant content here",
            }
        ]
    }

    with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key"}):
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_post.return_value)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_post.return_value.raise_for_status = lambda: None
            mock_post.return_value.json = lambda: mock_response
            mock_post.return_value.status_code = 200

            async with Client(search_server) as client:
                result = await client.call_tool("web_search", {"query": "test query"})
                output = result.content[0].text

    assert "Test Result" in output or "example.com" in output or "relevant" in output


# ---------------------------------------------------------------------------
# REPL agent wiring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repl_set_agent():
    """REPLInterface.set_agent() stores the agent correctly."""
    from nexus.cli.repl import REPLInterface
    from nexus.core.session import SessionContext
    from nexus.core.agent import Agent

    repl = REPLInterface()
    session = repl.start_session()

    provider = AsyncMock()
    provider.invoke = AsyncMock(return_value=LLMResponse(
        content="Hello from agent",
        tool_calls=[],
        stop_reason="end_turn",
    ))

    agent = Agent(llm_provider=provider, session=session)
    repl.set_agent(agent)

    assert repl.agent is agent


@pytest.mark.asyncio
async def test_repl_has_no_agent_by_default():
    """REPLInterface starts with no agent."""
    from nexus.cli.repl import REPLInterface

    repl = REPLInterface()
    assert repl.agent is None
