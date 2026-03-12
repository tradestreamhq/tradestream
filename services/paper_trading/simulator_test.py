"""Tests for the order execution simulator."""

import pytest

from services.paper_trading.models import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from services.paper_trading.simulator import OrderExecutionSimulator


@pytest.fixture
def prices():
    """Static price lookup."""
    return {
        "BTC-USD": 50000.0,
        "ETH-USD": 3000.0,
        "SOL-USD": 100.0,
    }


@pytest.fixture
def sim(prices):
    return OrderExecutionSimulator(
        initial_balance=100_000.0,
        price_fn=lambda s: prices.get(s),
        commission_rate=0.001,
        slippage_rate=0.0,
        max_position_pct=0.1,
    )


class TestMarketOrders:
    def test_buy_market_order_fills(self, sim):
        order = sim.submit_order("BTC-USD", OrderSide.BUY, 0.5, OrderType.MARKET)
        assert order.status == OrderStatus.FILLED
        pos = sim.portfolio.get_position("BTC-USD")
        assert pos is not None
        assert pos.quantity == 0.5

    def test_sell_market_order_fills(self, sim):
        sim.submit_order("BTC-USD", OrderSide.BUY, 1.0, OrderType.MARKET)
        order = sim.submit_order("BTC-USD", OrderSide.SELL, 0.5, OrderType.MARKET)
        assert order.status == OrderStatus.FILLED
        pos = sim.portfolio.get_position("BTC-USD")
        assert pos is not None
        assert pos.quantity == pytest.approx(0.5, abs=1e-8)

    def test_sell_full_position_removes_it(self, sim):
        sim.submit_order("BTC-USD", OrderSide.BUY, 1.0, OrderType.MARKET)
        sim.submit_order("BTC-USD", OrderSide.SELL, 1.0, OrderType.MARKET)
        assert sim.portfolio.get_position("BTC-USD") is None

    def test_buy_rejected_insufficient_funds(self, sim):
        order = sim.submit_order("BTC-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        assert order.status == OrderStatus.REJECTED

    def test_market_order_unknown_symbol_rejected(self, sim):
        order = sim.submit_order("FAKE-USD", OrderSide.BUY, 1.0, OrderType.MARKET)
        assert order.status == OrderStatus.REJECTED

    def test_cash_deducted_on_buy(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        # 10 * 100 = 1000, plus 0.1% commission = 1001
        expected_cash = 100_000.0 - 10.0 * 100.0 - 10.0 * 100.0 * 0.001
        assert sim.portfolio.cash == pytest.approx(expected_cash, abs=0.01)

    def test_cash_credited_on_sell(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        cash_after_buy = sim.portfolio.cash
        sim.submit_order("SOL-USD", OrderSide.SELL, 10.0, OrderType.MARKET)
        # Sell proceeds minus commission
        expected = cash_after_buy + 10.0 * 100.0 - 10.0 * 100.0 * 0.001
        assert sim.portfolio.cash == pytest.approx(expected, abs=0.01)


class TestLimitOrders:
    def test_limit_buy_below_market_stays_pending(self, sim):
        order = sim.submit_order(
            "BTC-USD", OrderSide.BUY, 0.1, OrderType.LIMIT, limit_price=45000.0
        )
        assert order.status == OrderStatus.PENDING
        assert len(sim.pending_orders) == 1

    def test_limit_buy_fills_when_price_drops(self, sim):
        sim.submit_order(
            "BTC-USD", OrderSide.BUY, 0.1, OrderType.LIMIT, limit_price=45000.0
        )
        fills = sim.check_limit_orders({"BTC-USD": 44000.0})
        assert len(fills) == 1
        assert fills[0].fill_price == 45000.0
        assert len(sim.pending_orders) == 0

    def test_limit_sell_fills_when_price_rises(self, sim):
        sim.submit_order("BTC-USD", OrderSide.BUY, 0.1, OrderType.MARKET)
        sim.submit_order(
            "BTC-USD", OrderSide.SELL, 0.1, OrderType.LIMIT, limit_price=55000.0
        )
        fills = sim.check_limit_orders({"BTC-USD": 56000.0})
        assert len(fills) == 1

    def test_limit_order_no_fill_if_price_not_met(self, sim):
        sim.submit_order(
            "BTC-USD", OrderSide.BUY, 0.1, OrderType.LIMIT, limit_price=45000.0
        )
        fills = sim.check_limit_orders({"BTC-USD": 50000.0})
        assert len(fills) == 0
        assert len(sim.pending_orders) == 1

    def test_limit_order_rejected_without_price(self, sim):
        order = sim.submit_order(
            "BTC-USD", OrderSide.BUY, 0.1, OrderType.LIMIT, limit_price=None
        )
        assert order.status == OrderStatus.REJECTED

    def test_cancel_pending_limit_order(self, sim):
        order = sim.submit_order(
            "BTC-USD", OrderSide.BUY, 0.1, OrderType.LIMIT, limit_price=45000.0
        )
        assert sim.cancel_order(order.order_id) is True
        assert order.status == OrderStatus.CANCELLED
        assert len(sim.pending_orders) == 0

    def test_cancel_nonexistent_order(self, sim):
        assert sim.cancel_order("nonexistent") is False

    def test_limit_buy_rejected_insufficient_funds(self, sim):
        sim.submit_order(
            "BTC-USD", OrderSide.BUY, 10.0, OrderType.LIMIT, limit_price=45000.0
        )
        fills = sim.check_limit_orders({"BTC-USD": 40000.0})
        assert len(fills) == 0
        order = list(sim._orders.values())[-1]
        assert order.status == OrderStatus.REJECTED


class TestSlippage:
    def test_buy_slippage_increases_price(self, prices):
        sim = OrderExecutionSimulator(
            initial_balance=100_000.0,
            price_fn=lambda s: prices.get(s),
            commission_rate=0.0,
            slippage_rate=0.001,
        )
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        pos = sim.portfolio.get_position("SOL-USD")
        assert pos.avg_cost_basis == pytest.approx(100.0 * 1.001, abs=0.01)

    def test_sell_slippage_decreases_price(self, prices):
        sim = OrderExecutionSimulator(
            initial_balance=100_000.0,
            price_fn=lambda s: prices.get(s),
            commission_rate=0.0,
            slippage_rate=0.001,
        )
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        sim.submit_order("SOL-USD", OrderSide.SELL, 10.0, OrderType.MARKET)
        # Should have small negative realized PnL from slippage
        assert sim.portfolio.total_realized_pnl() < 0


class TestPositionSizing:
    def test_compute_position_size(self, sim):
        size = sim.compute_position_size("BTC-USD")
        # 10% of 100k = 10k, at $50k per BTC = 0.2 BTC
        assert size == pytest.approx(0.2, abs=0.001)

    def test_position_size_zero_price(self, sim):
        assert sim.compute_position_size("FAKE-USD") == 0.0

    def test_position_size_after_trades(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 100.0, OrderType.MARKET)
        size = sim.compute_position_size("BTC-USD")
        # Cash reduced, so position size should be smaller
        assert size < 0.2


class TestPnLTracking:
    def test_realized_pnl_on_profitable_sell(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        # Change price and sell
        sim._price_fn = lambda s: {"SOL-USD": 110.0}.get(s)
        sim.submit_order("SOL-USD", OrderSide.SELL, 10.0, OrderType.MARKET)
        pnl = sim.portfolio.total_realized_pnl()
        # (110 - 100) * 10 = 100, minus commissions
        assert pnl > 0

    def test_realized_pnl_on_losing_sell(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        sim._price_fn = lambda s: {"SOL-USD": 90.0}.get(s)
        sim.submit_order("SOL-USD", OrderSide.SELL, 10.0, OrderType.MARKET)
        pnl = sim.portfolio.total_realized_pnl()
        assert pnl < 0

    def test_unrealized_pnl(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        upnl = sim.portfolio.unrealized_pnl({"SOL-USD": 120.0})
        # (120 - 100) * 10 = 200
        assert upnl == pytest.approx(200.0, abs=0.01)

    def test_unrealized_pnl_for_single_position(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        upnl = sim.portfolio.unrealized_pnl_for("SOL-USD", 120.0)
        assert upnl == pytest.approx(200.0, abs=0.01)

    def test_unrealized_pnl_for_missing_position(self, sim):
        assert sim.portfolio.unrealized_pnl_for("FAKE-USD", 100.0) == 0.0


class TestPerformanceTracking:
    def test_daily_snapshot(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        snap = sim.record_daily_snapshot("2026-03-12", {"SOL-USD": 105.0})
        assert snap.date == "2026-03-12"
        assert snap.ending_equity > snap.starting_equity
        assert snap.daily_pnl > 0
        assert snap.open_positions == 1
        assert snap.total_trades == 1

    def test_cumulative_return(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        ret = sim.portfolio.cumulative_return({"SOL-USD": 110.0})
        # Gain: (110-100)*10 = 100, minus commission ~1.0
        # Total equity ~ 100099, return ~ 0.099%
        assert ret > 0

    def test_multiple_snapshots(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        sim.record_daily_snapshot("2026-03-10", {"SOL-USD": 105.0})
        sim.record_daily_snapshot("2026-03-11", {"SOL-USD": 110.0})
        snapshots = sim.portfolio.daily_snapshots
        assert len(snapshots) == 2
        assert snapshots[1].starting_equity == snapshots[0].ending_equity

    def test_trade_log(self, sim):
        sim.submit_order("BTC-USD", OrderSide.BUY, 0.1, OrderType.MARKET)
        sim.submit_order("ETH-USD", OrderSide.BUY, 1.0, OrderType.MARKET)
        assert len(sim.trade_log) == 2
        assert sim.trade_log[0].symbol == "BTC-USD"
        assert sim.trade_log[1].symbol == "ETH-USD"


class TestSummary:
    def test_summary_output(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        s = sim.summary({"SOL-USD": 105.0})
        assert "cash" in s
        assert "total_equity" in s
        assert "unrealized_pnl" in s
        assert "realized_pnl" in s
        assert "cumulative_return_pct" in s
        assert s["open_positions"] == 1
        assert s["total_trades"] == 1


class TestMultiplePositions:
    def test_track_multiple_positions(self, sim):
        sim.submit_order("BTC-USD", OrderSide.BUY, 0.1, OrderType.MARKET)
        sim.submit_order("ETH-USD", OrderSide.BUY, 1.0, OrderType.MARKET)
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)

        positions = sim.portfolio.get_all_positions()
        assert len(positions) == 3
        symbols = {p.symbol for p in positions}
        assert symbols == {"BTC-USD", "ETH-USD", "SOL-USD"}

    def test_avg_cost_basis_multiple_buys(self, sim):
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)
        # Change price
        sim._price_fn = lambda s: {"SOL-USD": 120.0, "BTC-USD": 50000.0}.get(s)
        sim.submit_order("SOL-USD", OrderSide.BUY, 10.0, OrderType.MARKET)

        pos = sim.portfolio.get_position("SOL-USD")
        assert pos.quantity == 20.0
        # Avg = (100*10 + 120*10) / 20 = 110
        assert pos.avg_cost_basis == pytest.approx(110.0, abs=0.01)


class TestGetOrder:
    def test_get_existing_order(self, sim):
        order = sim.submit_order("SOL-USD", OrderSide.BUY, 1.0, OrderType.MARKET)
        fetched = sim.get_order(order.order_id)
        assert fetched is not None
        assert fetched.order_id == order.order_id

    def test_get_nonexistent_order(self, sim):
        assert sim.get_order("nonexistent") is None
