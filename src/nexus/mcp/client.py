"""MCP client manager for NEXUS."""

import time
from fastmcp import Client, FastMCP

from nexus.llm.provider import ToolSchema
from nexus.core.types import ToolResult


class MCPClientManager:
    """Manages connections to multiple MCP servers and routes tool calls."""

    def __init__(self):
        self._servers: dict[str, FastMCP] = {}
        self._tool_to_server: dict[str, str] = {}
        self._cached_schemas: list[ToolSchema] = []

    def register_server(self, name: str, server: FastMCP) -> None:
        """Register an MCP server under the given name."""
        self._servers[name] = server

    async def initialize(self) -> None:
        """Connect to all registered servers and cache their tool schemas."""
        self._cached_schemas = []
        self._tool_to_server = {}

        for server_name, server in self._servers.items():
            try:
                async with Client(server) as client:
                    tools = await client.list_tools()
                    for tool in tools:
                        self._tool_to_server[tool.name] = server_name
                        self._cached_schemas.append(
                            ToolSchema(
                                name=tool.name,
                                description=tool.description or "",
                                parameters=tool.inputSchema if tool.inputSchema else {
                                    "type": "object",
                                    "properties": {},
                                },
                            )
                        )
            except Exception as e:
                print(f"Warning: Failed to connect to MCP server '{server_name}': {e}")

    def get_tool_schemas(self) -> list[ToolSchema]:
        """Return the cached tool schemas from all registered servers."""
        return self._cached_schemas

    async def call_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """Route a tool call to the correct server and return the result."""
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return ToolResult(
                tool_call_id="",
                tool_name=tool_name,
                output=f"Tool not found: {tool_name}",
                success=False,
                error=f"No server registered for tool: {tool_name}",
            )

        server = self._servers[server_name]
        start = time.time()

        try:
            async with Client(server) as client:
                raw = await client.call_tool(tool_name, arguments)
                output = "\n".join(c.text for c in raw.content if hasattr(c, "text"))

            return ToolResult(
                tool_call_id="",
                tool_name=tool_name,
                output=output,
                success=True,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                tool_name=tool_name,
                output=str(e),
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )
