"""Tests for the rebalancing service (database interaction layer)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from services.portfolio_rebalancing.rebalancer import (
    AllocationTarget,
    RebalanceConstraints,
    TradeSide,
)
from services.portfolio_rebalancing.service import RebalancingService


class FakeRecord(dict):
    """Dict that also supports attribute-style access via __getitem__."""

    def __getitem__(self, key):
        return super().__getitem__(key)


def make_record(**kwargs):
    return FakeRecord(**kwargs)


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    return pool


@pytest.fixture
def service(mock_pool):
    return RebalancingService(mock_pool)


class TestGetCurrentHoldings:
    @pytest.mark.asyncio
    async def test_returns_holdings(self, service, mock_pool):
        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                make_record(
                    symbol="BTC-USD",
                    quantity=0.1,
                    avg_entry_price=50000.0,
                    unrealized_pnl=200.0,
                ),
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        holdings = await service.get_current_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "BTC-USD"
        assert holdings[0].quantity == 0.1
        assert holdings[0].market_value == 5000.0

    @pytest.mark.asyncio
    async def test_empty_portfolio(self, service, mock_pool):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        holdings = await service.get_current_holdings()
        assert holdings == []


class TestGetAvailableCash:
    @pytest.mark.asyncio
    async def test_computes_cash(self, service, mock_pool):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            side_effect=[
                make_record(total_invested=4000.0),
                make_record(total_realized=500.0),
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        cash = await service.get_available_cash(initial_capital=10000.0)
        assert cash == 6500.0  # 10000 + 500 - 4000


class TestGetTargetAllocation:
    @pytest.mark.asyncio
    async def test_loads_from_table(self, service, mock_pool):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)  # table exists
        conn.fetch = AsyncMock(
            return_value=[
                make_record(symbol="BTC-USD", target_pct=0.6),
                make_record(symbol="ETH-USD", target_pct=0.4),
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        targets = await service.get_target_allocation()
        assert len(targets) == 2
        assert targets[0].symbol == "BTC-USD"
        assert targets[0].target_pct == 0.6

    @pytest.mark.asyncio
    async def test_falls_back_to_equal_weight(self, service, mock_pool):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=False)  # table doesn't exist
        conn.fetch = AsyncMock(
            return_value=[
                make_record(
                    symbol="BTC-USD",
                    quantity=0.1,
                    avg_entry_price=50000.0,
                    unrealized_pnl=0.0,
                ),
                make_record(
                    symbol="ETH-USD",
                    quantity=2.0,
                    avg_entry_price=2500.0,
                    unrealized_pnl=0.0,
                ),
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        targets = await service.get_target_allocation()
        assert len(targets) == 2
        assert targets[0].target_pct == pytest.approx(0.5)
        assert targets[1].target_pct == pytest.approx(0.5)
