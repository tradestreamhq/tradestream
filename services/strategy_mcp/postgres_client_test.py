"""
Tests for the strategy MCP PostgreSQL client.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.strategy_mcp.postgres_client import PostgresClient


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
    async def test_get_top_strategies(self, postgres_client):
        """Test querying top strategies."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {
                "spec_name": "macd_crossover",
                "impl_id": "00000000-0000-0000-0000-000000000001",
                "score": 1.5,
                "parameters": json.dumps({"fast": 12, "slow": 26}),
                "strategy_type": "macd_crossover",
            }[key]
            mock_conn.fetch.return_value = [mock_row]

            await postgres_client.connect()
            result = await postgres_client.get_top_strategies(
                "BTC/USD", limit=5, min_score=0.5
            )

            assert len(result) == 1
            assert result[0]["spec_name"] == "macd_crossover"
            assert result[0]["score"] == 1.5

    @pytest.mark.asyncio
    async def test_get_spec_found(self, postgres_client):
        """Test getting a strategy spec that exists."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {
                "name": "macd_crossover",
                "indicators": {"macd": {"fast": 12}},
                "entry_conditions": {"cross_above": True},
                "exit_conditions": {"cross_below": True},
                "parameters": {"fast": {"min": 5, "max": 20}},
                "source": "MIGRATED",
            }[key]
            mock_conn.fetchrow.return_value = mock_row

            await postgres_client.connect()
            result = await postgres_client.get_spec("macd_crossover")

            assert result is not None
            assert result["name"] == "macd_crossover"
            assert result["source"] == "MIGRATED"

    @pytest.mark.asyncio
    async def test_get_spec_not_found(self, postgres_client):
        """Test getting a strategy spec that does not exist."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None

            await postgres_client.connect()
            result = await postgres_client.get_spec("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_performance(self, postgres_client):
        """Test getting performance metrics."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {
                "backtest_metrics": {"sharpe_ratio": 1.5, "max_drawdown": -0.1},
                "paper_metrics": None,
                "live_metrics": None,
            }[key]
            mock_row.get = lambda key: {
                "backtest_metrics": {"sharpe_ratio": 1.5, "max_drawdown": -0.1},
                "paper_metrics": None,
                "live_metrics": None,
            }.get(key)
            mock_conn.fetchrow.return_value = mock_row

            await postgres_client.connect()
            result = await postgres_client.get_performance(
                "00000000-0000-0000-0000-000000000001"
            )

            assert result is not None
            assert "backtest" in result

    @pytest.mark.asyncio
    async def test_get_performance_filtered(self, postgres_client):
        """Test getting performance metrics filtered by environment."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {
                "backtest_metrics": {"sharpe_ratio": 1.5},
                "paper_metrics": {"sharpe_ratio": 1.2},
                "live_metrics": None,
            }[key]
            mock_row.get = lambda key: {
                "backtest_metrics": {"sharpe_ratio": 1.5},
                "paper_metrics": {"sharpe_ratio": 1.2},
                "live_metrics": None,
            }.get(key)
            mock_conn.fetchrow.return_value = mock_row

            await postgres_client.connect()
            result = await postgres_client.get_performance(
                "00000000-0000-0000-0000-000000000001", environment="backtest"
            )

            assert "backtest" in result
            assert "paper" not in result

    @pytest.mark.asyncio
    async def test_list_strategy_types(self, postgres_client):
        """Test listing strategy types."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_row1 = MagicMock()
            mock_row1.__getitem__.side_effect = lambda key: {"name": "macd_crossover"}[
                key
            ]
            mock_row2 = MagicMock()
            mock_row2.__getitem__.side_effect = lambda key: {
                "name": "rsi_mean_reversion"
            }[key]
            mock_conn.fetch.return_value = [mock_row1, mock_row2]

            await postgres_client.connect()
            result = await postgres_client.list_strategy_types()

            assert result == ["macd_crossover", "rsi_mean_reversion"]

    @pytest.mark.asyncio
    async def test_create_spec(self, postgres_client):
        """Test creating a strategy spec."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            import uuid

            spec_id = uuid.uuid4()
            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {"id": spec_id}[key]
            mock_conn.fetchrow.return_value = mock_row

            await postgres_client.connect()
            result = await postgres_client.create_spec(
                name="test_spec",
                indicators={"rsi": {"period": 14}},
                entry_conditions={"rsi_below": 30},
                exit_conditions={"rsi_above": 70},
                parameters={"period": {"min": 5, "max": 30}},
                description="Test strategy",
            )

            assert "spec_id" in result
            assert result["spec_id"] == str(spec_id)

    @pytest.mark.asyncio
    async def test_get_walk_forward(self, postgres_client):
        """Test getting walk-forward results."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_row = MagicMock()
            mock_row.__getitem__.side_effect = lambda key: {
                "validation_status": "APPROVED",
                "sharpe_degradation": 0.15,
                "in_sample_sharpe": 2.0,
                "out_of_sample_sharpe": 1.7,
                "window_results": [{"window": 1, "sharpe": 1.6}],
            }[key]
            mock_conn.fetchrow.return_value = mock_row

            await postgres_client.connect()
            result = await postgres_client.get_walk_forward(
                "00000000-0000-0000-0000-000000000001"
            )

            assert result is not None
            assert result["validation_status"] == "APPROVED"
            assert result["sharpe_degradation"] == 0.15

    @pytest.mark.asyncio
    async def test_get_walk_forward_not_found(self, postgres_client):
        """Test getting walk-forward results when none exist."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None

            await postgres_client.connect()
            result = await postgres_client.get_walk_forward(
                "00000000-0000-0000-0000-000000000001"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_not_connected_raises(self, postgres_client):
        """Test that operations raise when not connected."""
        with pytest.raises(RuntimeError, match="PostgreSQL connection not established"):
            await postgres_client.get_top_strategies("BTC/USD")

        with pytest.raises(RuntimeError, match="PostgreSQL connection not established"):
            await postgres_client.get_spec("test")

        with pytest.raises(RuntimeError, match="PostgreSQL connection not established"):
            await postgres_client.list_strategy_types()
