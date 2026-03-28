"""
Tests for the Redis market client with mocked Redis.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.market_mcp.redis_client import RedisMarketClient


class TestRedisMarketClient:
    """Test cases for RedisMarketClient."""

    @pytest.fixture
    def client(self):
        """Create a RedisMarketClient with a mocked connection."""
        c = RedisMarketClient(host="localhost", port=6379)
        c.client = MagicMock()
        return c

    def test_connect_success(self):
        """Test successful Redis connection."""
        with patch("services.market_mcp.redis_client.redis.Redis") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            c = RedisMarketClient(host="localhost", port=6379)
            c.connect()

            mock_cls.assert_called_once_with(
                host="localhost", port=6379, decode_responses=True
            )
            mock_instance.ping.assert_called_once()

    def test_get_symbols(self, client):
        """Test get_symbols parses tiingo-format symbols."""
        client.client.get.return_value = json.dumps(["btcusd", "ethusd", "solusd"])

        result = client.get_symbols()

        assert len(result) == 3
        assert result[0]["id"] == "btcusd"
        assert result[0]["base"] == "BTC"
        assert result[0]["quote"] == "USD"
        assert result[0]["asset_class"] == "crypto"
        assert result[1]["base"] == "ETH"
        assert result[2]["base"] == "SOL"

    def test_get_symbols_empty(self, client):
        """Test get_symbols when Redis key is missing."""
        client.client.get.return_value = None
        result = client.get_symbols()
        assert result == []

    def test_get_symbols_non_usd_pair(self, client):
        """Test get_symbols with non-USD pair falls back to full string as base."""
        client.client.get.return_value = json.dumps(["btceur"])
        result = client.get_symbols()
        assert result[0]["base"] == "BTCEUR"
        assert result[0]["quote"] == "USD"

    def test_get_symbols_custom_key(self, client):
        """Test get_symbols with a custom Redis key."""
        client.client.get.return_value = json.dumps(["btcusd"])
        result = client.get_symbols(key="custom_key")
        client.client.get.assert_called_once_with("custom_key")
        assert len(result) == 1

    def test_get_symbols_default_key(self, client):
        """Test get_symbols uses top_cryptocurrencies key by default."""
        client.client.get.return_value = json.dumps([])
        client.get_symbols()
        client.client.get.assert_called_once_with("top_cryptocurrencies")

    def test_get_symbols_without_connection(self):
        """Test get_symbols without connecting raises RuntimeError."""
        c = RedisMarketClient(host="localhost", port=6379)
        with pytest.raises(RuntimeError, match="not established"):
            c.get_symbols()

    def test_close(self, client):
        """Test close calls client.close()."""
        client.close()
        client.client.close.assert_called_once()

    def test_close_no_connection(self):
        """Test close without connection doesn't raise."""
        c = RedisMarketClient(host="localhost", port=6379)
        c.close()  # Should not raise
