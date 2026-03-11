"""
Tests for the PostgreSQL client.
"""

import asyncio
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

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
    async def test_verify_schema_success(self, postgres_client):
        """Test schema verification when table exists."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchval.return_value = 1

            await postgres_client.connect()
            await postgres_client.verify_schema()

            assert mock_conn.fetchval.called

    @pytest.mark.asyncio
    async def test_verify_schema_missing_table(self, postgres_client):
        """Test schema verification when table is missing."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchval.return_value = 0

            await postgres_client.connect()
            with pytest.raises(RuntimeError, match="Strategies table not found"):
                await postgres_client.verify_schema()

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

    @pytest.mark.asyncio
    async def test_ensure_or_get_spec_creates_new(self, postgres_client):
        """Test ensure_or_get_spec creates a new spec when none exists."""
        spec_uuid = uuid.uuid4()
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # fetchrow returns the new spec id
            mock_conn.fetchrow.return_value = {"id": spec_uuid}

            await postgres_client.connect()
            result = await postgres_client.ensure_or_get_spec("MACD_CROSSOVER")

            assert result == spec_uuid
            # Should have called execute (upsert) and fetchrow (select)
            mock_conn.execute.assert_called_once()
            mock_conn.fetchrow.assert_called_once()
            # Verify the strategy type was passed
            execute_args = mock_conn.execute.call_args
            assert execute_args[0][1] == "MACD_CROSSOVER"

    @pytest.mark.asyncio
    async def test_ensure_or_get_spec_returns_existing(self, postgres_client):
        """Test ensure_or_get_spec returns existing spec on second call."""
        spec_uuid = uuid.uuid4()
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Both calls return the same UUID
            mock_conn.fetchrow.return_value = {"id": spec_uuid}

            await postgres_client.connect()
            result1 = await postgres_client.ensure_or_get_spec("MACD_CROSSOVER")
            result2 = await postgres_client.ensure_or_get_spec("MACD_CROSSOVER")

            assert result1 == spec_uuid
            assert result2 == spec_uuid

    @pytest.mark.asyncio
    async def test_insert_implementation(self, postgres_client):
        """Test insert_implementation creates a row linked to the spec."""
        spec_uuid = uuid.uuid4()
        impl_uuid = uuid.uuid4()
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {"id": impl_uuid}

            await postgres_client.connect()
            from datetime import datetime

            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 2)
            result = await postgres_client.insert_implementation(
                spec_id=spec_uuid,
                parameters={"fast_period": 12, "slow_period": 26},
                score=0.85,
                symbol="BTC/USD",
                start_time=start,
                end_time=end,
            )

            assert result == impl_uuid
            mock_conn.fetchrow.assert_called_once()
            # Verify spec_id was passed
            call_args = mock_conn.fetchrow.call_args
            assert call_args[0][1] == spec_uuid

    @pytest.mark.asyncio
    async def test_insert_strategies_writes_v2_model(self, postgres_client):
        """Test that insert_strategies also creates spec + impl rows."""
        spec_uuid = uuid.uuid4()
        impl_uuid = uuid.uuid4()
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # fetchrow is called for ensure_or_get_spec (select) and insert_implementation (RETURNING)
            mock_conn.fetchrow.side_effect = [
                {"id": spec_uuid},  # ensure_or_get_spec select
                {"id": impl_uuid},  # insert_implementation RETURNING
            ]

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
            # Should have calls for: flat table upsert, V2 spec upsert, V2 spec select (via fetchrow), V2 impl insert (via fetchrow)
            # execute called twice: flat table upsert + spec upsert
            assert mock_conn.execute.call_count == 2
            # fetchrow called twice: spec select + impl insert
            assert mock_conn.fetchrow.call_count == 2
