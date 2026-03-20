"""
Tests for the Strategy Knowledge Graph PostgreSQL client.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.strategy_knowledge_graph_mcp.postgres_client import PostgresClient


class TestPostgresClient:
    """Test cases for the strategy knowledge graph PostgreSQL client."""

    @pytest.fixture
    def client(self):
        """Create a PostgresClient with mock pool."""
        c = PostgresClient(
            host="localhost",
            port=5432,
            database="test",
            username="user",
            password="pass",
        )
        c.pool = AsyncMock()
        return c

    @pytest.fixture
    def mock_conn(self, client):
        """Create and wire a mock connection."""
        conn = AsyncMock()
        client.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        client.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        return conn

    def test_ensure_pool_raises_without_connection(self):
        """Test that _ensure_pool raises when pool is None."""
        c = PostgresClient("h", 5432, "db", "u", "p")
        with pytest.raises(RuntimeError, match="not established"):
            c._ensure_pool()

    @pytest.mark.asyncio
    async def test_get_indicator_relationships(self, client, mock_conn):
        """Test get_indicator_relationships returns formatted results."""
        mock_conn.fetch.return_value = [
            {
                "indicator_a": "RSI",
                "category_a": "momentum",
                "indicator_b": "MACD",
                "category_b": "momentum",
                "relationship_type": "complementary",
                "strength": 0.8,
                "reasoning": "RSI + MACD confirmation",
            }
        ]

        result = await client.get_indicator_relationships(
            indicator_name="RSI", limit=10
        )

        assert result["count"] == 1
        assert result["items"][0]["indicator_a"] == "RSI"
        assert result["items"][0]["strength"] == 0.8

    @pytest.mark.asyncio
    async def test_get_indicator_relationships_no_filter(self, client, mock_conn):
        """Test get_indicator_relationships without filters."""
        mock_conn.fetch.return_value = []

        result = await client.get_indicator_relationships()

        assert result["count"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_get_complementary_indicators(self, client, mock_conn):
        """Test get_complementary_indicators."""
        mock_conn.fetch.return_value = [
            {
                "complementary_indicator": "MACD",
                "category": "momentum",
                "strength": 0.8,
                "reasoning": "Confirmation signal",
            }
        ]

        result = await client.get_complementary_indicators("RSI", min_strength=0.5)

        assert result["indicator"] == "RSI"
        assert len(result["complementary"]) == 1
        assert result["complementary"][0]["indicator"] == "MACD"

    @pytest.mark.asyncio
    async def test_get_market_conditions_filtered(self, client, mock_conn):
        """Test get_market_conditions with filters."""
        mock_conn.fetch.return_value = [
            {
                "id": "cond-uuid",
                "trend": "trending_up",
                "volatility": "medium",
                "volume": "high",
                "sentiment": "bullish",
                "description": "Steady uptrend",
            }
        ]

        result = await client.get_market_conditions(
            trend="trending_up", volatility="medium"
        )

        assert result["count"] == 1
        assert result["items"][0]["trend"] == "trending_up"

    @pytest.mark.asyncio
    async def test_get_market_conditions_no_filter(self, client, mock_conn):
        """Test get_market_conditions without filters returns all."""
        mock_conn.fetch.return_value = [
            {"id": "c1", "trend": "trending_up", "volatility": "high", "volume": "high", "sentiment": "bullish", "description": "d1"},
            {"id": "c2", "trend": "ranging", "volatility": "low", "volume": "low", "sentiment": "neutral", "description": "d2"},
        ]

        result = await client.get_market_conditions()
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_recommend_strategies(self, client, mock_conn):
        """Test recommend_strategies returns ranked results."""
        mock_conn.fetch.return_value = [
            {
                "spec_id": "spec-uuid",
                "spec_name": "MACD_TREND",
                "indicators": '[{"type": "MACD"}]',
                "description": "MACD trend following",
                "trend": "trending_up",
                "volatility": "medium",
                "volume": "high",
                "sentiment": "bullish",
                "condition_description": "Steady uptrend",
                "sample_size": 150,
                "win_rate": 0.62,
                "avg_return": 0.035,
                "sharpe_ratio": 1.8,
                "max_drawdown": -0.12,
                "instrument": "BTC/USD",
            }
        ]

        result = await client.recommend_strategies(
            trend="trending_up", volatility="medium", volume="high"
        )

        assert result["count"] == 1
        assert result["market_condition"]["trend"] == "trending_up"
        assert result["recommendations"][0]["spec_name"] == "MACD_TREND"
        assert result["recommendations"][0]["performance"]["sharpe_ratio"] == 1.8

    @pytest.mark.asyncio
    async def test_recommend_strategies_with_instrument(self, client, mock_conn):
        """Test recommend_strategies with instrument filter."""
        mock_conn.fetch.return_value = []

        result = await client.recommend_strategies(
            trend="ranging", volatility="low", volume="low", instrument="ETH/USD"
        )

        assert result["count"] == 0
        assert result["recommendations"] == []

    @pytest.mark.asyncio
    async def test_create_composite_strategy(self, client, mock_conn):
        """Test create_composite_strategy creates successfully."""
        mock_conn.fetchrow.side_effect = [
            None,  # no duplicate
            {"id": "comp-uuid"},  # INSERT RETURNING
        ]
        mock_conn.execute.return_value = "INSERT 0 1"
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await client.create_composite_strategy(
            name="test_ensemble",
            description="Test ensemble",
            component_spec_ids=["spec-1", "spec-2"],
            weights=[0.6, 0.4],
        )

        assert result["created"] is True
        assert result["components_count"] == 2

    @pytest.mark.asyncio
    async def test_create_composite_strategy_duplicate(self, client, mock_conn):
        """Test create_composite_strategy with duplicate name."""
        mock_conn.fetchrow.return_value = {"id": "existing-uuid"}

        result = await client.create_composite_strategy(
            name="existing",
            description="Test",
            component_spec_ids=["spec-1"],
        )

        assert result["created"] is False
        assert "already exists" in result["error"]

    @pytest.mark.asyncio
    async def test_create_composite_strategy_weight_mismatch(self, client):
        """Test create_composite_strategy with mismatched weights."""
        result = await client.create_composite_strategy(
            name="test",
            description="Test",
            component_spec_ids=["spec-1", "spec-2"],
            weights=[0.5],  # wrong length
        )

        assert result["created"] is False
        assert "weights length" in result["error"]

    @pytest.mark.asyncio
    async def test_get_composite_strategy(self, client, mock_conn):
        """Test get_composite_strategy returns full composite details."""
        mock_conn.fetchrow.return_value = {
            "id": "comp-uuid",
            "name": "test_ensemble",
            "description": "Test",
            "combination_method": "weighted_average",
            "min_agreement": 0.5,
            "is_active": True,
            "created_at": "2026-01-01",
        }
        mock_conn.fetch.return_value = [
            {
                "strategy_spec_id": "spec-uuid",
                "spec_name": "RSI_REVERSAL",
                "indicators": '[{"type": "RSI"}]',
                "weight": 0.6,
                "role": "signal",
            }
        ]

        result = await client.get_composite_strategy("comp-uuid")

        assert result is not None
        assert result["name"] == "test_ensemble"
        assert len(result["components"]) == 1

    @pytest.mark.asyncio
    async def test_get_composite_strategy_not_found(self, client, mock_conn):
        """Test get_composite_strategy returns None when not found."""
        mock_conn.fetchrow.return_value = None

        result = await client.get_composite_strategy("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_composite_strategies(self, client, mock_conn):
        """Test list_composite_strategies."""
        mock_conn.fetch.return_value = [
            {
                "id": "comp-uuid",
                "name": "test_ensemble",
                "description": "Test",
                "combination_method": "weighted_average",
                "is_active": True,
                "components_count": 3,
            }
        ]

        result = await client.list_composite_strategies(active_only=True)

        assert result["count"] == 1
        assert result["items"][0]["components_count"] == 3

    @pytest.mark.asyncio
    async def test_get_performance_attribution(self, client, mock_conn):
        """Test get_performance_attribution."""
        mock_conn.fetch.return_value = [
            {
                "component_name": "RSI_REVERSAL",
                "component_spec_id": "spec-uuid",
                "instrument": "BTC/USD",
                "total_signals": 100,
                "total_agreed": 75,
                "total_pnl": 1250.5,
                "avg_contribution_pct": 0.45,
                "avg_accuracy": 0.62,
            }
        ]

        result = await client.get_performance_attribution("comp-uuid")

        assert result["count"] == 1
        assert result["attributions"][0]["total_pnl"] == 1250.5

    @pytest.mark.asyncio
    async def test_explore_strategy_graph(self, client, mock_conn):
        """Test explore_strategy_graph returns complete graph data."""
        mock_conn.fetchrow.return_value = {
            "id": "spec-uuid",
            "name": "RSI_REVERSAL",
            "indicators": '[{"type": "RSI"}]',
            "entry_conditions": '[{"type": "UNDER_CONSTANT"}]',
            "exit_conditions": '[{"type": "OVER_CONSTANT"}]',
            "description": "RSI mean reversion",
        }
        # tags fetch, composites fetch, conditions fetch
        mock_conn.fetch.side_effect = [
            [{"tag": "mean_reversion"}, {"tag": "momentum"}],
            [
                {
                    "id": "comp-uuid",
                    "name": "momentum_ensemble",
                    "weight": 0.5,
                    "role": "signal",
                }
            ],
            [
                {
                    "trend": "ranging",
                    "volatility": "medium",
                    "volume": "medium",
                    "sentiment": "neutral",
                    "sharpe_ratio": 2.1,
                    "win_rate": 0.65,
                    "sample_size": 200,
                    "instrument": "BTC/USD",
                }
            ],
        ]

        result = await client.explore_strategy_graph("spec-uuid")

        assert result is not None
        assert result["name"] == "RSI_REVERSAL"
        assert len(result["tags"]) == 2
        assert "mean_reversion" in result["tags"]
        assert len(result["composites"]) == 1
        assert len(result["best_conditions"]) == 1

    @pytest.mark.asyncio
    async def test_explore_strategy_graph_not_found(self, client, mock_conn):
        """Test explore_strategy_graph returns None when not found."""
        mock_conn.fetchrow.return_value = None

        result = await client.explore_strategy_graph("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_strategies(self, client, mock_conn):
        """Test find_similar_strategies."""
        mock_conn.fetch.return_value = [
            {
                "spec_id": "spec-005",
                "name": "STOCHASTIC_REVERSAL",
                "description": "Stochastic-based",
                "indicators": '[{"type": "STOCHASTIC"}]',
                "tag_overlap": 2,
                "indicator_overlap": 0,
                "similarity_score": 2,
            }
        ]

        result = await client.find_similar_strategies("spec-001")

        assert result["count"] == 1
        assert result["similar"][0]["name"] == "STOCHASTIC_REVERSAL"
        assert result["similar"][0]["similarity_score"] == 2
