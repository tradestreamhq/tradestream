"""Tests for the web search MCP server."""

import json
import pytest
from unittest.mock import MagicMock, patch

from services.websearch_mcp.search_client import (
    SearchClient,
    RateLimiter,
    build_financial_query,
    _extract_domain,
    FINANCIAL_DOMAINS,
)
from services.websearch_mcp.server import create_server


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False


class TestBuildFinancialQuery:
    def test_bitcoin_general(self):
        q = build_financial_query("BTC/USD", "general")
        assert "Bitcoin" in q
        assert "news" in q

    def test_ethereum_regulatory(self):
        q = build_financial_query("ETH", "regulatory")
        assert "Ethereum" in q
        assert "SEC" in q

    def test_unknown_asset(self):
        q = build_financial_query("AAPL", "sentiment")
        assert "AAPL" in q
        assert "sentiment" in q

    def test_default_topic(self):
        q = build_financial_query("BTC/USD")
        assert "Bitcoin" in q


class TestExtractDomain:
    def test_basic(self):
        assert _extract_domain("https://www.reuters.com/article/123") == "reuters.com"

    def test_no_www(self):
        assert _extract_domain("https://coindesk.com/news") == "coindesk.com"


class TestSearchClient:
    def test_rate_limit_error(self):
        client = SearchClient(brave_api_key="test")
        client._rate_limiter = RateLimiter(max_requests=0, window_seconds=60)
        with pytest.raises(RuntimeError, match="Rate limit"):
            client.search("test query")

    def test_no_provider_error(self):
        client = SearchClient()
        with pytest.raises(RuntimeError, match="No search provider"):
            client.search("test query")


class TestWebSearchMcpServer:
    @pytest.fixture
    def search_client(self):
        client = MagicMock(spec=SearchClient)
        client.search.return_value = [
            {
                "title": "Bitcoin hits new high",
                "url": "https://reuters.com/article/btc",
                "snippet": "Bitcoin reached a new all-time high today.",
                "source": "reuters.com",
                "published_at": "2h ago",
            },
        ]
        return client

    @pytest.fixture
    def server(self, search_client):
        return create_server(search_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        result = await list_tools_handler(MagicMock())
        tool_names = [t.name for t in result.tools]
        assert "web_search" in tool_names
        assert "financial_search" in tool_names

    @pytest.mark.asyncio
    async def test_web_search(self, server, search_client):
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "web_search"
        request.params.arguments = {"query": "Bitcoin ETF approval"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "data" in response
        assert "_metadata" in response
        assert response["data"]["count"] == 1
        assert response["data"]["results"][0]["title"] == "Bitcoin hits new high"
        assert response["_metadata"]["source"] == "web_search"
        assert response["_metadata"]["cached"] is False

    @pytest.mark.asyncio
    async def test_web_search_empty_query(self, server):
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "web_search"
        request.params.arguments = {"query": ""}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "error" in response
        assert response["error"]["code"] == "INVALID_QUERY"

    @pytest.mark.asyncio
    async def test_financial_search(self, server, search_client):
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "financial_search"
        request.params.arguments = {
            "instrument": "BTC/USD",
            "topic": "regulatory",
        }

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "data" in response
        assert response["data"]["instrument"] == "BTC/USD"
        assert response["data"]["topic"] == "regulatory"
        assert "Bitcoin" in response["data"]["query"]
        assert "SEC" in response["data"]["query"]
        search_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_web_search_cached(self, server, search_client):
        """Test that repeated search returns cached result."""
        call_tool_handler = server.request_handlers.get("tools/call")

        request = MagicMock()
        request.params.name = "web_search"
        request.params.arguments = {"query": "test cache"}

        # First call
        await call_tool_handler(request)
        # Second call (should be cached)
        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["_metadata"]["cached"] is True
        assert response["_metadata"]["cache_ttl_remaining"] is not None
        # Search client should only be called once (second was cached)
        assert search_client.search.call_count == 1

    @pytest.mark.asyncio
    async def test_web_search_force_refresh(self, server, search_client):
        """Test force_refresh bypasses cache."""
        call_tool_handler = server.request_handlers.get("tools/call")

        request = MagicMock()
        request.params.name = "web_search"
        request.params.arguments = {"query": "test force refresh"}

        # First call
        await call_tool_handler(request)

        # Second call with force_refresh
        request.params.arguments = {
            "query": "test force refresh",
            "force_refresh": True,
        }
        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["_metadata"]["cached"] is False
        assert search_client.search.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limited_error(self, server, search_client):
        search_client.search.side_effect = RuntimeError("Rate limit exceeded: 10 requests per minute")

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "web_search"
        request.params.arguments = {"query": "test rate limit"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "error" in response
        assert response["error"]["code"] == "RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "nonexistent"
        request.params.arguments = {}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "error" in response
        assert response["error"]["code"] == "UNKNOWN_TOOL"
