"""
Tests for the PostgreSQL client.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.strategy_consumer.postgres_client import PostgresClient


class TestPostgresClient:
    """Test cases for PostgresClient."""

    @pytest.fixture
    def postgres_client(self):
        """Create a PostgresClient instance for testing."""
        return PostgresClient(
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user",
            password="test_password",
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, postgres_client):
        """Test successful connection to PostgreSQL."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            # Mock the connection test
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            await postgres_client.connect()

            assert postgres_client.pool is not None
            mock_create_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, postgres_client):
        """Test connection failure to PostgreSQL."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_create_pool.side_effect = Exception("Connection failed")

            with pytest.raises(Exception):
                await postgres_client.connect()

            assert postgres_client.pool is None

    @pytest.mark.asyncio
    async def test_close(self, postgres_client):
        """Test closing the connection pool."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            await postgres_client.connect()
            await postgres_client.close()

            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_table_exists(self, postgres_client):
        """Test table creation."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            await postgres_client.connect()
            await postgres_client.ensure_table_exists()

            # Verify that execute was called (table creation SQL)
            assert mock_conn.execute.called

    @pytest.mark.asyncio
    async def test_insert_strategies_success(self, postgres_client):
        """Test successful strategy insertion."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            await postgres_client.connect()

            strategies = [
                {
                    "symbol": "BTC/USD",
                    "strategy_type": "MACD_CROSSOVER",
                    "parameters": {"fast_period": 12, "slow_period": 26},
                    "current_score": 0.85,
                    "strategy_hash": "hash123",
                    "discovery_symbol": "BTC/USD",
                    "discovery_start_time": "2024-01-01T00:00:00Z",
                    "discovery_end_time": "2024-01-01T01:00:00Z",
                }
            ]

            result = await postgres_client.insert_strategies(strategies)

            assert result == 1
            assert mock_conn.execute.called

    @pytest.mark.asyncio
    async def test_insert_strategies_empty_list(self, postgres_client):
        """Test insertion with empty strategy list."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            await postgres_client.connect()

            result = await postgres_client.insert_strategies([])

            assert result == 0

    @pytest.mark.asyncio
    async def test_get_strategy_count(self, postgres_client):
        """Test getting strategy count."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchval.return_value = 42

            await postgres_client.connect()

            result = await postgres_client.get_strategy_count()

            assert result == 42
            mock_conn.fetchval.assert_called_once_with(
                "SELECT COUNT(*) FROM Strategies"
            )

    @pytest.mark.asyncio
    async def test_get_strategies_by_symbol(self, postgres_client):
        """Test getting strategies by symbol."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Mock the fetch result
            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {
                "symbol": "BTC/USD",
                "strategy_type": "MACD_CROSSOVER",
                "parameters": json.dumps({"fast_period": 12}),
                "current_score": 0.85,
                "strategy_hash": "hash123",
                "discovery_symbol": "BTC/USD",
                "discovery_start_time": None,
                "discovery_end_time": None,
                "first_discovered_at": None,
                "last_evaluated_at": None,
            }[key]

            mock_conn.fetch.return_value = [mock_row]

            await postgres_client.connect()

            result = await postgres_client.get_strategies_by_symbol("BTC/USD")

            assert len(result) == 1
            assert result[0]["symbol"] == "BTC/USD"
            assert result[0]["strategy_type"] == "MACD_CROSSOVER"
