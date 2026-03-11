"""Tests for the shared MCP client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.shared.mcp_client import call_mcp_tool, resolve_and_call


class TestCallMcpTool:
    """Tests for call_mcp_tool."""

    @patch("services.shared.mcp_client.requests.post")
    def test_parsed_response_with_text_content(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": '{"symbols": ["BTC"]}'}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = call_mcp_tool("get_symbols", {}, "http://localhost:8081")

        assert result == {"symbols": ["BTC"]}
        mock_post.assert_called_once_with(
            "http://localhost:8081/call-tool",
            json={"name": "get_symbols", "arguments": {}},
            timeout=30,
        )

    @patch("services.shared.mcp_client.requests.post")
    def test_string_response_with_text_content(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": '{"symbols": ["BTC"]}'}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = call_mcp_tool(
            "get_symbols", {}, "http://localhost:8081", return_type="string"
        )

        assert result == '{"symbols": ["BTC"]}'

    @patch("services.shared.mcp_client.requests.post")
    def test_parsed_response_non_json_text(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "not json"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = call_mcp_tool("get_symbols", {}, "http://localhost:8081")

        assert result == {"raw": "not json"}

    @patch("services.shared.mcp_client.requests.post")
    def test_no_content_field(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = call_mcp_tool("get_symbols", {}, "http://localhost:8081")

        assert result == {"result": "ok"}

    @patch("services.shared.mcp_client.requests.post")
    def test_request_error_parsed(self, mock_post):
        mock_post.side_effect = Exception("connection refused")

        result = call_mcp_tool("get_symbols", {}, "http://localhost:8081")

        assert "error" in result

    @patch("services.shared.mcp_client.requests.post")
    def test_request_error_string(self, mock_post):
        mock_post.side_effect = Exception("connection refused")

        result = call_mcp_tool(
            "get_symbols", {}, "http://localhost:8081", return_type="string"
        )

        parsed = json.loads(result)
        assert "error" in parsed

    @patch("services.shared.mcp_client.requests.post")
    def test_url_trailing_slash_stripped(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        call_mcp_tool("test", {}, "http://localhost:8081/")

        mock_post.assert_called_once_with(
            "http://localhost:8081/call-tool",
            json={"name": "test", "arguments": {}},
            timeout=30,
        )

    @patch("services.shared.mcp_client.requests.post")
    def test_custom_timeout(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        call_mcp_tool("test", {}, "http://localhost:8081", timeout=10)

        mock_post.assert_called_once_with(
            "http://localhost:8081/call-tool",
            json={"name": "test", "arguments": {}},
            timeout=10,
        )

    @patch("services.shared.mcp_client.requests.post")
    def test_multiple_text_items_joined(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [
                {"type": "text", "text": "line1"},
                {"type": "text", "text": "line2"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = call_mcp_tool(
            "test", {}, "http://localhost:8081", return_type="string"
        )

        assert result == "line1\nline2"


class TestResolveAndCall:
    """Tests for resolve_and_call."""

    def test_unknown_tool(self):
        result = resolve_and_call(
            "unknown_tool", {}, {"known": "server"}, {"server": "http://localhost"}
        )
        assert result == {"error": "Unknown tool: unknown_tool"}

    def test_unknown_tool_string(self):
        result = resolve_and_call(
            "unknown_tool",
            {},
            {"known": "server"},
            {"server": "http://localhost"},
            return_type="string",
        )
        parsed = json.loads(result)
        assert parsed == {"error": "Unknown tool: unknown_tool"}

    def test_missing_server_url(self):
        result = resolve_and_call("get_symbols", {}, {"get_symbols": "market"}, {})
        assert result == {"error": "No URL configured for MCP server: market"}

    @patch("services.shared.mcp_client.requests.post")
    def test_successful_dispatch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": '{"data": 1}'}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        tool_to_server = {"get_symbols": "market"}
        mcp_urls = {"market": "http://localhost:8081"}

        result = resolve_and_call("get_symbols", {}, tool_to_server, mcp_urls)

        assert result == {"data": 1}
        mock_post.assert_called_once_with(
            "http://localhost:8081/call-tool",
            json={"name": "get_symbols", "arguments": {}},
            timeout=30,
        )
