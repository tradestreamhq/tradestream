"""
Integration tests for PostgreSQL client using testing.postgresql.
Tests actual database operations with a real PostgreSQL instance.
"""

import asyncio
import json
import pytest
import testing.postgresql
from datetime import datetime, timezone

from services.strategy_consumer.postgres_client import PostgresClient


class TestPostgresClientIntegration:
    """Integration tests for PostgresClient using real PostgreSQL instance."""

    @pytest.fixture
    def postgresql(self):
        """Create a temporary PostgreSQL instance for testing."""
        postgresql = testing.postgresql.Postgresql()
        yield postgresql
        postgresql.stop()

    @pytest.fixture
    def postgres_client(self, postgresql):
        """Create a PostgresClient instance connected to the test database."""
        return PostgresClient(
            host=postgresql.dsn()["host"],
            port=postgresql.dsn()["port"],
            database=postgresql.dsn()["database"],
            username=postgresql.dsn()["user"],
            password=postgresql.dsn()["password"],
        )

    @pytest.mark.asyncio
    async def test_connect_and_create_table(self, postgres_client):
        """Test connecting to PostgreSQL and creating the strategies table."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # Verify the table was created
        async with postgres_client.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'strategies'"
            )
            assert result == 1

    @pytest.mark.asyncio
    async def test_insert_strategies_with_timezone_aware_datetimes(self, postgres_client):
        """Test inserting strategies with timezone-aware datetime strings."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # Test data with timezone-aware datetime strings (like what we get from protobuf)
        strategies = [
            {
                "symbol": "BTC/USD",
                "strategy_type": "MACD_CROSSOVER",
                "parameters": {"fast_period": 12, "slow_period": 26},
                "current_score": 0.85,
                "strategy_hash": "hash123",
                "discovery_symbol": "BTC/USD",
                "discovery_start_time": "2024-01-01T00:00:00+00:00",  # Timezone-aware
                "discovery_end_time": "2024-01-01T01:00:00+00:00",    # Timezone-aware
            },
            {
                "symbol": "ETH/USD",
                "strategy_type": "RSI_EMA_CROSSOVER",
                "parameters": {"rsi_period": 14, "ema_period": 20},
                "current_score": 0.92,
                "strategy_hash": "hash456",
                "discovery_symbol": "ETH/USD",
                "discovery_start_time": "2024-01-01T02:00:00Z",  # Z format
                "discovery_end_time": "2024-01-01T03:00:00Z",    # Z format
            },
        ]

        # This should not raise any timezone-related errors
        processed_count = await postgres_client.insert_strategies(strategies)
        assert processed_count == 2

        # Verify the strategies were inserted correctly
        async with postgres_client.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM strategies ORDER BY symbol")
            assert len(rows) == 2

            # Check first strategy
            btc_row = rows[0]
            assert btc_row["symbol"] == "BTC/USD"
            assert btc_row["strategy_type"] == "MACD_CROSSOVER"
            assert btc_row["current_score"] == 0.85
            assert btc_row["strategy_hash"] == "hash123"
            assert btc_row["discovery_symbol"] == "BTC/USD"
            
            # Check that timestamps were stored correctly (timezone-naive)
            assert btc_row["discovery_start_time"] is not None
            assert btc_row["discovery_end_time"] is not None
            # Verify they are timezone-naive
            assert btc_row["discovery_start_time"].tzinfo is None
            assert btc_row["discovery_end_time"].tzinfo is None

            # Check second strategy
            eth_row = rows[1]
            assert eth_row["symbol"] == "ETH/USD"
            assert eth_row["strategy_type"] == "RSI_EMA_CROSSOVER"
            assert eth_row["current_score"] == 0.92
            assert eth_row["strategy_hash"] == "hash456"

    @pytest.mark.asyncio
    async def test_insert_strategies_with_null_timestamps(self, postgres_client):
        """Test inserting strategies with null timestamp values."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        strategies = [
            {
                "symbol": "SOL/USD",
                "strategy_type": "BBAND_WR",
                "parameters": {"period": 20, "std_dev": 2},
                "current_score": 0.78,
                "strategy_hash": "hash789",
                "discovery_symbol": "SOL/USD",
                "discovery_start_time": None,  # Null timestamp
                "discovery_end_time": None,    # Null timestamp
            }
        ]

        processed_count = await postgres_client.insert_strategies(strategies)
        assert processed_count == 1

        # Verify the strategy was inserted correctly
        async with postgres_client.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM strategies WHERE symbol = 'SOL/USD'")
            assert row is not None
            assert row["symbol"] == "SOL/USD"
            assert row["discovery_start_time"] is None
            assert row["discovery_end_time"] is None

    @pytest.mark.asyncio
    async def test_upsert_logic(self, postgres_client):
        """Test that upsert logic works correctly (insert then update)."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # Insert initial strategy
        initial_strategy = {
            "symbol": "ADA/USD",
            "strategy_type": "STOCHASTIC_EMA",
            "parameters": {"k_period": 14, "d_period": 3},
            "current_score": 0.75,
            "strategy_hash": "hash_upsert_test",
            "discovery_symbol": "ADA/USD",
            "discovery_start_time": "2024-01-01T00:00:00+00:00",
            "discovery_end_time": "2024-01-01T01:00:00+00:00",
        }

        processed_count = await postgres_client.insert_strategies([initial_strategy])
        assert processed_count == 1

        # Try to insert the same strategy with a different score (should update)
        updated_strategy = {
            "symbol": "ADA/USD",
            "strategy_type": "STOCHASTIC_EMA",
            "parameters": {"k_period": 14, "d_period": 3},
            "current_score": 0.90,  # Updated score
            "strategy_hash": "hash_upsert_test",  # Same hash
            "discovery_symbol": "ADA/USD",
            "discovery_start_time": "2024-01-01T00:00:00+00:00",
            "discovery_end_time": "2024-01-01T01:00:00+00:00",
        }

        processed_count = await postgres_client.insert_strategies([updated_strategy])
        assert processed_count == 1

        # Verify only one record exists with updated score
        async with postgres_client.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM strategies WHERE strategy_hash = 'hash_upsert_test'")
            assert count == 1

            row = await conn.fetchrow("SELECT * FROM strategies WHERE strategy_hash = 'hash_upsert_test'")
            assert row["current_score"] == 0.90  # Should have updated score

    @pytest.mark.asyncio
    async def test_get_strategy_count(self, postgres_client):
        """Test getting the total strategy count."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # Insert some test strategies
        strategies = [
            {
                "symbol": "XRP/USD",
                "strategy_type": "VWAP_CROSSOVER",
                "parameters": {"period": 20},
                "current_score": 0.82,
                "strategy_hash": "hash_count_1",
                "discovery_symbol": "XRP/USD",
            },
            {
                "symbol": "DOT/USD",
                "strategy_type": "VWAP_MEAN_REVERSION",
                "parameters": {"period": 50},
                "current_score": 0.79,
                "strategy_hash": "hash_count_2",
                "discovery_symbol": "DOT/USD",
            },
        ]

        await postgres_client.insert_strategies(strategies)
        count = await postgres_client.get_strategy_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_strategies_by_symbol(self, postgres_client):
        """Test getting strategies by symbol."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # Insert test strategies
        strategies = [
            {
                "symbol": "LINK/USD",
                "strategy_type": "MACD_CROSSOVER",
                "parameters": {"fast_period": 12, "slow_period": 26},
                "current_score": 0.88,
                "strategy_hash": "hash_link_1",
                "discovery_symbol": "LINK/USD",
            },
            {
                "symbol": "LINK/USD",  # Same symbol, different strategy
                "strategy_type": "RSI_EMA_CROSSOVER",
                "parameters": {"rsi_period": 14, "ema_period": 20},
                "current_score": 0.85,
                "strategy_hash": "hash_link_2",
                "discovery_symbol": "LINK/USD",
            },
        ]

        await postgres_client.insert_strategies(strategies)
        link_strategies = await postgres_client.get_strategies_by_symbol("LINK/USD")
        
        assert len(link_strategies) == 2
        assert all(s["symbol"] == "LINK/USD" for s in link_strategies)
        assert link_strategies[0]["current_score"] == 0.88  # Should be sorted by score DESC
        assert link_strategies[1]["current_score"] == 0.85

    @pytest.mark.asyncio
    async def test_error_handling_invalid_json(self, postgres_client):
        """Test error handling when parameters contain invalid JSON."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # This should not crash the entire batch
        strategies = [
            {
                "symbol": "TEST/USD",
                "strategy_type": "TEST_STRATEGY",
                "parameters": {"invalid": "data"},  # This should be fine
                "current_score": 0.50,
                "strategy_hash": "hash_test",
                "discovery_symbol": "TEST/USD",
            }
        ]

        processed_count = await postgres_client.insert_strategies(strategies)
        assert processed_count == 1

    @pytest.mark.asyncio
    async def test_error_handling_missing_required_fields(self, postgres_client):
        """Test error handling when required fields are missing."""
        await postgres_client.connect()
        await postgres_client.ensure_table_exists()

        # Strategy missing required fields should be skipped
        strategies = [
            {
                "symbol": "INVALID/USD",
                # Missing strategy_type, parameters, etc.
                "current_score": 0.50,
                "strategy_hash": "hash_invalid",
            }
        ]

        # This should handle the error gracefully and continue
        processed_count = await postgres_client.insert_strategies(strategies)
        assert processed_count == 0  # Should skip invalid strategy

        # Verify no invalid data was inserted
        async with postgres_client.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM strategies WHERE symbol = 'INVALID/USD'")
            assert count == 0 