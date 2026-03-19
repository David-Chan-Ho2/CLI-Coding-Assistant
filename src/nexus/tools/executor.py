"""MCP-backed tool executor for NEXUS."""

from nexus.core.agent import ToolExecutor
from nexus.core.types import ToolCall, ToolResult
from nexus.llm.provider import ToolSchema
from nexus.mcp.client import MCPClientManager


class MCPToolExecutor(ToolExecutor):
    """Tool executor that routes calls through the MCP client manager."""

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp_manager = mcp_manager

    async def initialize(self) -> None:
        """Initialize the MCP manager and discover available tools."""
        await self.mcp_manager.initialize()

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call via the MCP manager."""
        result = await self.mcp_manager.call_tool(tool_call.name, tool_call.arguments)
        result.tool_call_id = tool_call.id
        return result

    def get_tool_schemas(self) -> list[ToolSchema]:
        """Return available tool schemas from the MCP manager."""
        return self.mcp_manager.get_tool_schemas()
