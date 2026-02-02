"""Base MCP server implementation using stdio transport."""

import json
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from .errors import MCPError, error_response


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]


@dataclass
class MCPResponse:
    """Standard MCP response with metadata."""

    data: Any
    latency_ms: int
    cached: bool = False
    cache_ttl_remaining: Optional[int] = None
    source: str = "postgresql"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "_metadata": {
                "latency_ms": self.latency_ms,
                "cached": self.cached,
                "cache_ttl_remaining": self.cache_ttl_remaining,
                "source": self.source,
            },
        }


class BaseMCPServer(ABC):
    """Base class for MCP servers using stdio transport (JSON-RPC)."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, ToolDefinition] = {}
        self._setup_tools()

    @abstractmethod
    def _setup_tools(self) -> None:
        """Register tools for this server. Override in subclasses."""
        pass

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register a tool with the server."""
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get JSON schemas for all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters,
            }
            for tool in self.tools.values()
        ]

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        start_time = time.time()

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tool_call(params)
            else:
                raise MCPError(
                    code="INVALID_PARAMETER",
                    message=f"Unknown method: {method}",
                )

            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }

        except MCPError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": error_response(e, latency_ms),
            }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                    "_metadata": {"latency_ms": latency_ms},
                },
            }

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    def _handle_tools_list(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": self.get_tool_schemas()}

    def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            raise MCPError(
                code="NOT_FOUND",
                message=f"Tool not found: {tool_name}",
                details={"tool_name": tool_name},
            )

        tool = self.tools[tool_name]
        start_time = time.time()

        try:
            result = tool.handler(**arguments)
            latency_ms = int((time.time() - start_time) * 1000)

            # Check if result is already an MCPResponse
            if isinstance(result, MCPResponse):
                result.latency_ms = latency_ms
                return {"content": [{"type": "text", "text": json.dumps(result.to_dict())}]}

            # Wrap raw result
            response = MCPResponse(data=result, latency_ms=latency_ms)
            return {"content": [{"type": "text", "text": json.dumps(response.to_dict())}]}

        except MCPError:
            raise
        except Exception as e:
            raise MCPError(
                code="DATABASE_ERROR",
                message=str(e),
            )

    def run_stdio(self) -> None:
        """Run the server using stdio transport."""
        sys.stderr.write(f"Starting {self.name} MCP server v{self.version}\n")
        sys.stderr.flush()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}",
                    },
                }
                print(json.dumps(error_response), flush=True)
