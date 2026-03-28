"""Tests for MCPClient."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.agents.mcp_client import MCPClient


class TestMCPClient:
    """Tests for the MCP routing client."""

    def test_default_urls(self):
        client = MCPClient()
        assert "strategy-mcp" in client.get_url("strategy")
        assert "market-mcp" in client.get_url("market")
        assert "signal-mcp" in client.get_url("signal")

    def test_custom_urls(self):
        urls = {
            "strategy": "http://custom-strategy:9000",
            "market": "http://custom-market:9000",
            "signal": "http://custom-signal:9000",
        }
        client = MCPClient(urls=urls)
        assert client.get_url("strategy") == "http://custom-strategy:9000"
        assert client.get_url("market") == "http://custom-market:9000"
        assert client.get_url("signal") == "http://custom-signal:9000"

    def test_env_var_override(self):
        with patch.dict(
            "os.environ",
            {"STRATEGY_MCP_URL": "http://env-strategy:7000"},
        ):
            client = MCPClient()
            assert client.get_url("strategy") == "http://env-strategy:7000"

    def test_unknown_server_raises(self):
        client = MCPClient()
        with pytest.raises(ValueError, match="Unknown MCP server"):
            client.get_url("nonexistent")

    @patch("services.agents.mcp_client.requests.post")
    def test_call_tool_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": '{"result": "ok"}'}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MCPClient(urls={"strategy": "http://localhost:8080"})
        result = client.call_tool(
            "strategy", "get_top_strategies", {"symbol": "BTC-USD"}
        )

        assert result == {"result": "ok"}
        mock_post.assert_called_once_with(
            "http://localhost:8080/call-tool",
            json={"name": "get_top_strategies", "arguments": {"symbol": "BTC-USD"}},
            timeout=30,
        )

    @patch("services.agents.mcp_client.requests.post")
    def test_call_tool_raw_text_fallback(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "not json"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MCPClient(urls={"market": "http://localhost:8080"})
        result = client.call_tool("market", "get_market_summary", {"symbol": "ETH-USD"})

        assert result == {"raw": "not json"}

    @patch("services.agents.mcp_client.requests.post")
    def test_call_tool_request_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.ConnectionError("connection refused")

        client = MCPClient(urls={"signal": "http://localhost:8080"})
        result = client.call_tool("signal", "get_recent_signals", {})

        assert "error" in result

    @patch("services.agents.mcp_client.requests.post")
    def test_call_tool_no_text_content(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"content": [{"type": "image", "data": "..."}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MCPClient(urls={"strategy": "http://localhost:8080"})
        result = client.call_tool("strategy", "some_tool", {})

        assert result == {"content": [{"type": "image", "data": "..."}]}

    @patch("services.agents.mcp_client.requests.post")
    def test_call_tool_custom_timeout(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"content": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MCPClient(urls={"market": "http://localhost:8080"})
        client.call_tool("market", "slow_tool", {}, timeout=120)

        mock_post.assert_called_once_with(
            "http://localhost:8080/call-tool",
            json={"name": "slow_tool", "arguments": {}},
            timeout=120,
        )

    def test_partial_custom_urls(self):
        """Only override one URL; others fall back to defaults."""
        client = MCPClient(urls={"strategy": "http://custom:9000"})
        assert client.get_url("strategy") == "http://custom:9000"
        assert "market-mcp" in client.get_url("market")
