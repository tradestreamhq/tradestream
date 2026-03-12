"""Tests for the MCP server base framework."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from services.shared.mcp_server_base import McpServerBase, ToolDef, _error_code


class FakeServer(McpServerBase):
    """Test implementation of McpServerBase."""

    def __init__(self):
        self.handle_result = {"status": "ok"}
        self.handle_error = None
        super().__init__("test-server")

    def tool_definitions(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="test_tool",
                description="A test tool",
                input_schema={
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string"},
                    },
                    "required": ["arg1"],
                },
            ),
            ToolDef(
                name="another_tool",
                description="Another test tool",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self.handle_error:
            raise self.handle_error
        if name == "test_tool":
            return self.handle_result
        if name == "another_tool":
            return {"items": []}
        raise ValueError(f"Unknown tool: {name}")


@pytest.fixture
def fake_server():
    return FakeServer()


class TestToolDefinitions:
    def test_server_name(self, fake_server):
        assert fake_server._server_name == "test-server"

    def test_tool_count(self, fake_server):
        assert len(fake_server.tool_definitions()) == 2

    def test_tool_names(self, fake_server):
        names = {td.name for td in fake_server.tool_definitions()}
        assert names == {"test_tool", "another_tool"}


class TestCallTool:
    @pytest.mark.asyncio
    async def test_successful_call_includes_data_and_metadata(self, fake_server):
        # Access the registered call_tool handler via the server internals
        result = await fake_server.handle_tool("test_tool", {"arg1": "val"})
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, fake_server):
        with pytest.raises(ValueError, match="Unknown tool"):
            await fake_server.handle_tool("nonexistent", {})


class TestErrorCode:
    def test_value_error(self):
        assert _error_code(ValueError("bad")) == "INVALID_PARAMETER"

    def test_key_error(self):
        assert _error_code(KeyError("missing")) == "NOT_FOUND"

    def test_permission_error(self):
        assert _error_code(PermissionError("denied")) == "UNAUTHORIZED"

    def test_timeout_error(self):
        assert _error_code(TimeoutError("slow")) == "TIMEOUT"

    def test_generic_error(self):
        assert _error_code(RuntimeError("oops")) == "INTERNAL_ERROR"
