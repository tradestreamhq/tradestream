"""Base MCP server framework for TradeStream subsystems.

Provides a standardized way to create MCP servers that wrap existing
subsystem functionality. Each subsystem defines its tools and handlers,
and this framework handles transport, error formatting, and response metadata.

Usage:
    from services.shared.mcp_server_base import McpServerBase, ToolDef

    class MySubsystemServer(McpServerBase):
        def __init__(self, client):
            super().__init__("my-subsystem")
            self._client = client

        def tool_definitions(self) -> list[ToolDef]:
            return [
                ToolDef(
                    name="get_data",
                    description="Fetch data from the subsystem",
                    input_schema={
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    },
                ),
            ]

        async def handle_tool(self, name: str, arguments: dict) -> dict:
            if name == "get_data":
                return await self._client.get_data(arguments["id"])
            raise ValueError(f"Unknown tool: {name}")
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    """Definition of an MCP tool exposed by a subsystem server."""

    name: str
    description: str
    input_schema: dict[str, Any]


class McpServerBase(ABC):
    """Base class for TradeStream MCP servers.

    Subclasses define their tools and handlers. This base class handles:
    - Tool registration with the MCP Server
    - Error formatting with structured error codes
    - Response metadata (latency, source)
    - Transport setup (stdio or SSE)
    """

    def __init__(self, server_name: str) -> None:
        self._server = Server(server_name)
        self._server_name = server_name
        self._register_handlers()

    @property
    def server(self) -> Server:
        """Access the underlying MCP Server instance."""
        return self._server

    @abstractmethod
    def tool_definitions(self) -> list[ToolDef]:
        """Return the list of tools this server exposes."""

    @abstractmethod
    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle a tool call. Return a JSON-serializable result."""

    def _register_handlers(self) -> None:
        """Register list_tools and call_tool handlers on the MCP server."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name=td.name,
                    description=td.description,
                    inputSchema=td.input_schema,
                )
                for td in self.tool_definitions()
            ]

        @self._server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent]:
            start = time.monotonic()
            try:
                result = await self.handle_tool(name, arguments)
                latency_ms = round((time.monotonic() - start) * 1000, 1)
                response = {
                    "data": result,
                    "_metadata": {
                        "latency_ms": latency_ms,
                        "source": self._server_name,
                    },
                }
                return [
                    TextContent(
                        type="text", text=json.dumps(response, default=str)
                    )
                ]
            except Exception as e:
                latency_ms = round((time.monotonic() - start) * 1000, 1)
                logger.error(
                    "Tool %s failed on %s: %s", name, self._server_name, e
                )
                error_response = {
                    "error": {
                        "code": _error_code(e),
                        "message": str(e),
                    },
                    "_metadata": {
                        "latency_ms": latency_ms,
                        "source": self._server_name,
                    },
                }
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(error_response, default=str),
                    )
                ]


def _error_code(exc: Exception) -> str:
    """Map exception types to structured error codes."""
    if isinstance(exc, ValueError):
        return "INVALID_PARAMETER"
    if isinstance(exc, KeyError):
        return "NOT_FOUND"
    if isinstance(exc, PermissionError):
        return "UNAUTHORIZED"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    return "INTERNAL_ERROR"
