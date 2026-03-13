"""Tests for the Order Execution Simulator engine."""

import pytest

from services.order_simulator.models import (
    FeeSchedule,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    SlippageConfig,
    SlippageModel,
)
from services.order_simulator.simulator import OrderSimulator


def _make_order(**kwargs):
    defaults = dict(
        instrument="BTC/USD",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=1.0,
    )
    defaults.update(kwargs)
    return SimulatedOrder(**defaults)


class TestPlaceOrder:
    def test_market_order_placed(self):
        sim = OrderSimulator()
        order = _make_order()
        result = sim.place_order(order)
        assert result.status == OrderStatus.OPEN
        assert result.id in sim.orders

    def test_limit_order_requires_price(self):
        sim = OrderSimulator()
        order = _make_order(order_type=OrderType.LIMIT, price=None)
        with pytest.raises(ValueError, match="require a price"):
            sim.place_order(order)

    def test_stop_loss_requires_price(self):
        sim = OrderSimulator()
        order = _make_order(order_type=OrderType.STOP_LOSS, price=None)
        with pytest.raises(ValueError, match="require a price"):
            sim.place_order(order)

    def test_take_profit_requires_price(self):
        sim = OrderSimulator()
        order = _make_order(order_type=OrderType.TAKE_PROFIT, price=None)
        with pytest.raises(ValueError, match="require a price"):
            sim.place_order(order)

    def test_limit_order_with_price(self):
        sim = OrderSimulator()
        order = _make_order(order_type=OrderType.LIMIT, price=50000.0)
        result = sim.place_order(order)
        assert result.status == OrderStatus.OPEN


class TestCancelOrder:
    def test_cancel_open_order(self):
        sim = OrderSimulator()
        order = _make_order()
        sim.place_order(order)
        result = sim.cancel_order(order.id)
        assert result is not None
        assert result.status == OrderStatus.CANCELLED

    def test_cancel_nonexistent_order(self):
        sim = OrderSimulator()
        assert sim.cancel_order("nonexistent") is None

    def test_cancel_already_cancelled(self):
        sim = OrderSimulator()
        order = _make_order()
        sim.place_order(order)
        sim.cancel_order(order.id)
        assert sim.cancel_order(order.id) is None


class TestMarketOrderFill:
    def test_buy_market_order_fills(self):
        sim = OrderSimulator(initial_balance=100_000.0)
        order = _make_order(quantity=0.1)
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=49_990.0, ask=50_010.0)
        assert len(fills) == 1
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == pytest.approx(0.1, abs=1e-6)
        assert fills[0].fee > 0

    def test_sell_market_order_fills(self):
        sim = OrderSimulator(initial_balance=100_000.0)
        # First buy to establish position
        buy = _make_order(side=OrderSide.BUY, quantity=1.0)
        sim.place_order(buy)
        sim.process_market_tick("BTC/USD", bid=49_990.0, ask=50_010.0)

        # Now sell
        sell = _make_order(side=OrderSide.SELL, quantity=0.5)
        sim.place_order(sell)
        fills = sim.process_market_tick("BTC/USD", bid=51_000.0, ask=51_020.0)
        assert len(fills) == 1
        assert sell.status == OrderStatus.FILLED

    def test_buy_insufficient_balance(self):
        sim = OrderSimulator(initial_balance=100.0)
        order = _make_order(quantity=1.0)
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=49_990.0, ask=50_010.0)
        assert len(fills) == 0
        assert order.status == OrderStatus.OPEN

    def test_sell_insufficient_position(self):
        sim = OrderSimulator()
        order = _make_order(side=OrderSide.SELL, quantity=1.0)
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)
        assert len(fills) == 0


class TestLimitOrderFill:
    def test_buy_limit_fills_at_or_below(self):
        sim = OrderSimulator()
        order = _make_order(
            order_type=OrderType.LIMIT, side=OrderSide.BUY,
            price=50_000.0, quantity=0.1
        )
        sim.place_order(order)

        # Price above limit — should not fill
        fills = sim.process_market_tick("BTC/USD", bid=50_500.0, ask=50_510.0)
        assert len(fills) == 0

        # Price at limit — should fill
        fills = sim.process_market_tick("BTC/USD", bid=49_990.0, ask=50_000.0)
        assert len(fills) == 1
        assert order.status == OrderStatus.FILLED

    def test_sell_limit_fills_at_or_above(self):
        sim = OrderSimulator()
        # Buy first
        buy = _make_order(side=OrderSide.BUY, quantity=1.0)
        sim.place_order(buy)
        sim.process_market_tick("BTC/USD", bid=49_990.0, ask=50_010.0)

        sell = _make_order(
            order_type=OrderType.LIMIT, side=OrderSide.SELL,
            price=51_000.0, quantity=0.5
        )
        sim.place_order(sell)

        # Price below limit — should not fill
        fills = sim.process_market_tick("BTC/USD", bid=50_500.0, ask=50_510.0)
        assert len(fills) == 0

        # Price at limit — should fill
        fills = sim.process_market_tick("BTC/USD", bid=51_000.0, ask=51_010.0)
        assert len(fills) == 1
        assert sell.status == OrderStatus.FILLED


class TestStopLossOrderFill:
    def test_sell_stop_loss_triggers_below(self):
        sim = OrderSimulator()
        buy = _make_order(side=OrderSide.BUY, quantity=1.0)
        sim.place_order(buy)
        sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)

        stop = _make_order(
            order_type=OrderType.STOP_LOSS, side=OrderSide.SELL,
            price=49_000.0, quantity=0.5
        )
        sim.place_order(stop)

        # Price above stop — no fill
        fills = sim.process_market_tick("BTC/USD", bid=49_500.0, ask=49_510.0)
        assert len(fills) == 0

        # Price at/below stop — fill
        fills = sim.process_market_tick("BTC/USD", bid=48_900.0, ask=48_910.0)
        assert len(fills) == 1
        assert stop.status == OrderStatus.FILLED


class TestTakeProfitOrderFill:
    def test_sell_take_profit_triggers_above(self):
        sim = OrderSimulator()
        buy = _make_order(side=OrderSide.BUY, quantity=1.0)
        sim.place_order(buy)
        sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)

        tp = _make_order(
            order_type=OrderType.TAKE_PROFIT, side=OrderSide.SELL,
            price=52_000.0, quantity=0.5
        )
        sim.place_order(tp)

        # Price below target — no fill
        fills = sim.process_market_tick("BTC/USD", bid=51_000.0, ask=51_010.0)
        assert len(fills) == 0

        # Price at/above target — fill
        fills = sim.process_market_tick("BTC/USD", bid=52_100.0, ask=52_110.0)
        assert len(fills) == 1
        assert tp.status == OrderStatus.FILLED


class TestPartialFills:
    def test_partial_fill_by_volume(self):
        sim = OrderSimulator(max_fill_ratio=0.3)
        order = _make_order(quantity=10.0)
        sim.place_order(order)

        # Volume of 10 means max fill is 3.0
        fills = sim.process_market_tick(
            "BTC/USD", bid=50_000.0, ask=50_010.0, volume=10.0
        )
        assert len(fills) == 1
        assert order.filled_quantity == pytest.approx(3.0, abs=1e-6)
        assert order.status == OrderStatus.PARTIALLY_FILLED

        # Second tick fills more
        fills = sim.process_market_tick(
            "BTC/USD", bid=50_000.0, ask=50_010.0, volume=10.0
        )
        assert len(fills) == 1
        assert order.filled_quantity == pytest.approx(6.0, abs=1e-6)


class TestSlippageModels:
    def test_fixed_slippage_buy(self):
        config = SlippageConfig(model=SlippageModel.FIXED, value=10.0)
        sim = OrderSimulator(slippage_config=config)
        order = _make_order(quantity=0.01)
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)
        assert len(fills) == 1
        assert fills[0].fill_price == pytest.approx(50_020.0, abs=0.01)

    def test_fixed_slippage_sell(self):
        config = SlippageConfig(model=SlippageModel.FIXED, value=10.0)
        sim = OrderSimulator(slippage_config=config)
        buy = _make_order(quantity=1.0)
        sim.place_order(buy)
        sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)

        sell = _make_order(side=OrderSide.SELL, quantity=0.5)
        sim.place_order(sell)
        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)
        assert len(fills) == 1
        assert fills[0].fill_price == pytest.approx(49_990.0, abs=0.01)

    def test_percentage_slippage(self):
        config = SlippageConfig(model=SlippageModel.PERCENTAGE, value=0.01)
        sim = OrderSimulator(slippage_config=config)
        order = _make_order(quantity=0.01)
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_000.0)
        assert len(fills) == 1
        expected = 50_000.0 + 50_000.0 * 0.01
        assert fills[0].fill_price == pytest.approx(expected, abs=0.01)


class TestFeeSchedule:
    def test_taker_fee_on_market_order(self):
        fee_sched = FeeSchedule(maker_fee=0.001, taker_fee=0.002)
        config = SlippageConfig(model=SlippageModel.FIXED, value=0.0)
        sim = OrderSimulator(fee_schedule=fee_sched, slippage_config=config)
        order = _make_order(quantity=0.1)
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_000.0)
        assert len(fills) == 1
        expected_fee = 0.1 * 50_000.0 * 0.002
        assert fills[0].fee == pytest.approx(expected_fee, abs=0.01)

    def test_maker_fee_on_limit_order(self):
        fee_sched = FeeSchedule(maker_fee=0.001, taker_fee=0.002)
        config = SlippageConfig(model=SlippageModel.FIXED, value=0.0)
        sim = OrderSimulator(fee_schedule=fee_sched, slippage_config=config)
        order = _make_order(
            order_type=OrderType.LIMIT, price=50_000.0, quantity=0.1
        )
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=49_990.0, ask=50_000.0)
        assert len(fills) == 1
        expected_fee = 0.1 * 50_000.0 * 0.001
        assert fills[0].fee == pytest.approx(expected_fee, abs=0.01)


class TestOrderExpiration:
    def test_expired_order_not_filled(self):
        sim = OrderSimulator()
        order = _make_order(expires_at="2020-01-01T00:00:00+00:00")
        sim.place_order(order)
        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)
        assert len(fills) == 0
        assert order.status == OrderStatus.EXPIRED


class TestBalanceTracking:
    def test_balance_decreases_on_buy(self):
        config = SlippageConfig(model=SlippageModel.FIXED, value=0.0)
        fee_sched = FeeSchedule(maker_fee=0.0, taker_fee=0.0)
        sim = OrderSimulator(
            initial_balance=100_000.0,
            slippage_config=config,
            fee_schedule=fee_sched,
        )
        order = _make_order(quantity=1.0)
        sim.place_order(order)
        sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_000.0)
        assert sim.cash_balance == pytest.approx(50_000.0, abs=0.01)
        assert sim.positions["BTC/USD"] == pytest.approx(1.0, abs=1e-6)

    def test_balance_increases_on_sell(self):
        config = SlippageConfig(model=SlippageModel.FIXED, value=0.0)
        fee_sched = FeeSchedule(maker_fee=0.0, taker_fee=0.0)
        sim = OrderSimulator(
            initial_balance=100_000.0,
            slippage_config=config,
            fee_schedule=fee_sched,
        )
        buy = _make_order(quantity=1.0)
        sim.place_order(buy)
        sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_000.0)

        sell = _make_order(side=OrderSide.SELL, quantity=1.0)
        sim.place_order(sell)
        sim.process_market_tick("BTC/USD", bid=55_000.0, ask=55_010.0)
        assert sim.cash_balance == pytest.approx(105_000.0, abs=0.01)
        assert "BTC/USD" not in sim.positions

    def test_get_balance_summary(self):
        sim = OrderSimulator(initial_balance=100_000.0)
        summary = sim.get_balance_summary()
        assert summary["cash_balance"] == 100_000.0
        assert summary["initial_balance"] == 100_000.0
        assert summary["positions"] == {}
        assert summary["open_order_count"] == 0


class TestPositionTracking:
    def test_average_price_updates_on_additional_buy(self):
        config = SlippageConfig(model=SlippageModel.FIXED, value=0.0)
        fee_sched = FeeSchedule(maker_fee=0.0, taker_fee=0.0)
        sim = OrderSimulator(
            initial_balance=200_000.0,
            slippage_config=config,
            fee_schedule=fee_sched,
        )
        buy1 = _make_order(quantity=1.0)
        sim.place_order(buy1)
        sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_000.0)

        buy2 = _make_order(quantity=1.0)
        sim.place_order(buy2)
        sim.process_market_tick("BTC/USD", bid=60_000.0, ask=60_000.0)

        assert sim.positions["BTC/USD"] == pytest.approx(2.0, abs=1e-6)
        assert sim.position_avg_prices["BTC/USD"] == pytest.approx(55_000.0, abs=0.01)


class TestGetOrders:
    def test_get_open_orders(self):
        sim = OrderSimulator()
        o1 = _make_order(quantity=0.1)
        o2 = _make_order(quantity=0.1, instrument="ETH/USD")
        sim.place_order(o1)
        sim.place_order(o2)
        assert len(sim.get_open_orders()) == 2
        assert len(sim.get_open_orders(instrument="BTC/USD")) == 1

    def test_get_all_orders_includes_cancelled(self):
        sim = OrderSimulator()
        o1 = _make_order(quantity=0.1)
        sim.place_order(o1)
        sim.cancel_order(o1.id)
        assert len(sim.get_all_orders()) == 1
        assert len(sim.get_open_orders()) == 0


class TestDifferentInstruments:
    def test_orders_only_fill_matching_instrument(self):
        sim = OrderSimulator()
        btc = _make_order(instrument="BTC/USD", quantity=0.01)
        eth = _make_order(instrument="ETH/USD", quantity=0.1)
        sim.place_order(btc)
        sim.place_order(eth)

        fills = sim.process_market_tick("BTC/USD", bid=50_000.0, ask=50_010.0)
        assert len(fills) == 1
        assert btc.status == OrderStatus.FILLED
        assert eth.status == OrderStatus.OPEN
