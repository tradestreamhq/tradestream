"""Tests for the order execution simulator."""

import os
import tempfile

import pytest

from services.paper_trading.order_simulator import (
    FeeSchedule,
    Fill,
    OrderSide,
    OrderSimulator,
    OrderStatus,
    OrderType,
    Position,
    SimulatorConfig,
    SlippageConfig,
    SlippageModel,
)
from services.paper_trading.order_simulator_config import (
    default_config,
    load_config,
    load_config_from_string,
)


class TestFeeSchedule:
    def test_taker_fee(self):
        fees = FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002)
        fee = fees.calculate_fee(10000.0, is_maker=False)
        assert fee == 20.0

    def test_maker_fee(self):
        fees = FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002)
        fee = fees.calculate_fee(10000.0, is_maker=True)
        assert fee == 10.0

    def test_min_fee_applied(self):
        fees = FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002, min_fee=5.0)
        fee = fees.calculate_fee(100.0, is_maker=True)
        assert fee == 5.0  # 100 * 0.001 = 0.1, but min is 5.0

    def test_zero_notional(self):
        fees = FeeSchedule()
        assert fees.calculate_fee(0.0, is_maker=True) == 0.0


class TestSlippageConfig:
    def test_percentage_slippage_buy(self):
        slippage = SlippageConfig(
            model=SlippageModel.PERCENTAGE, value=0.01, randomize=False
        )
        result = slippage.apply(50000.0, OrderSide.BUY)
        assert result == 50500.0  # 1% above

    def test_percentage_slippage_sell(self):
        slippage = SlippageConfig(
            model=SlippageModel.PERCENTAGE, value=0.01, randomize=False
        )
        result = slippage.apply(50000.0, OrderSide.SELL)
        assert result == 49500.0  # 1% below

    def test_fixed_slippage_buy(self):
        slippage = SlippageConfig(
            model=SlippageModel.FIXED, value=10.0, randomize=False
        )
        result = slippage.apply(50000.0, OrderSide.BUY)
        assert result == 50010.0

    def test_fixed_slippage_sell(self):
        slippage = SlippageConfig(
            model=SlippageModel.FIXED, value=10.0, randomize=False
        )
        result = slippage.apply(50000.0, OrderSide.SELL)
        assert result == 49990.0

    def test_zero_slippage(self):
        slippage = SlippageConfig(value=0.0)
        assert slippage.apply(50000.0, OrderSide.BUY) == 50000.0

    def test_randomized_slippage_within_bounds(self):
        slippage = SlippageConfig(
            model=SlippageModel.PERCENTAGE, value=0.01, randomize=True
        )
        for _ in range(100):
            result = slippage.apply(50000.0, OrderSide.BUY)
            assert 50000.0 <= result <= 50500.0


class TestSimulatorConfig:
    def test_from_dict_defaults(self):
        config = SimulatorConfig.from_dict({})
        assert config.slippage.model == SlippageModel.PERCENTAGE
        assert config.slippage.value == 0.001
        assert config.fees.taker_fee_rate == 0.002
        assert config.fees.maker_fee_rate == 0.001

    def test_from_dict_custom(self):
        config = SimulatorConfig.from_dict(
            {
                "slippage": {"model": "FIXED", "value": 5.0, "randomize": False},
                "fees": {
                    "maker_fee_rate": 0.0005,
                    "taker_fee_rate": 0.001,
                    "min_fee": 1.0,
                },
            }
        )
        assert config.slippage.model == SlippageModel.FIXED
        assert config.slippage.value == 5.0
        assert config.fees.min_fee == 1.0


class TestMarketOrders:
    def setup_method(self):
        self.config = SimulatorConfig(
            slippage=SlippageConfig(
                model=SlippageModel.PERCENTAGE, value=0.001, randomize=False
            ),
            fees=FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002),
        )
        self.sim = OrderSimulator(self.config)

    def test_market_buy_order(self):
        fill = self.sim.submit_market_order(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.1,
            current_price=50000.0,
        )
        # Price should be 50000 * 1.001 = 50050 (0.1% slippage)
        assert fill.fill_price == 50050.0
        assert fill.quantity == 0.1
        assert fill.side == "BUY"
        # Notional = 50050 * 0.1 = 5005
        assert fill.notional == 5005.0
        # Fee = 5005 * 0.002 = 10.01 (taker)
        assert fill.fee == 10.01
        assert fill.slippage > 0

    def test_market_sell_order(self):
        fill = self.sim.submit_market_order(
            symbol="BTC-USD",
            side=OrderSide.SELL,
            quantity=0.1,
            current_price=50000.0,
        )
        # Price should be 50000 * 0.999 = 49950 (0.1% slippage)
        assert fill.fill_price == 49950.0
        assert fill.side == "SELL"

    def test_market_order_invalid_quantity(self):
        with pytest.raises(ValueError, match="quantity must be positive"):
            self.sim.submit_market_order(
                symbol="BTC-USD",
                side=OrderSide.BUY,
                quantity=0,
                current_price=50000.0,
            )

    def test_market_order_invalid_price(self):
        with pytest.raises(ValueError, match="current_price must be positive"):
            self.sim.submit_market_order(
                symbol="BTC-USD",
                side=OrderSide.BUY,
                quantity=0.1,
                current_price=-1.0,
            )


class TestLimitOrders:
    def setup_method(self):
        self.config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002),
        )
        self.sim = OrderSimulator(self.config)

    def test_submit_limit_buy(self):
        order = self.sim.submit_limit_order(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.5,
            limit_price=48000.0,
        )
        assert order.status == OrderStatus.PENDING
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 48000.0

    def test_limit_buy_fills_when_price_drops(self):
        self.sim.submit_limit_order(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.5,
            limit_price=48000.0,
        )
        # Price above limit - should not fill
        fills = self.sim.check_limit_orders("BTC-USD", 49000.0)
        assert len(fills) == 0

        # Price at limit - should fill
        fills = self.sim.check_limit_orders("BTC-USD", 48000.0)
        assert len(fills) == 1
        assert fills[0].fill_price == 48000.0
        # Maker fee
        expected_fee = 48000.0 * 0.5 * 0.001
        assert fills[0].fee == expected_fee

    def test_limit_sell_fills_when_price_rises(self):
        self.sim.submit_limit_order(
            symbol="BTC-USD",
            side=OrderSide.SELL,
            quantity=0.5,
            limit_price=52000.0,
        )
        # Price below limit - should not fill
        fills = self.sim.check_limit_orders("BTC-USD", 51000.0)
        assert len(fills) == 0

        # Price at limit - should fill
        fills = self.sim.check_limit_orders("BTC-USD", 52000.0)
        assert len(fills) == 1
        assert fills[0].fill_price == 52000.0

    def test_limit_buy_fills_below_limit(self):
        self.sim.submit_limit_order(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.5,
            limit_price=48000.0,
        )
        fills = self.sim.check_limit_orders("BTC-USD", 47000.0)
        assert len(fills) == 1
        # Fills at limit price, not market price
        assert fills[0].fill_price == 48000.0

    def test_limit_order_for_different_symbol_not_filled(self):
        self.sim.submit_limit_order(
            symbol="ETH-USD",
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=3000.0,
        )
        fills = self.sim.check_limit_orders("BTC-USD", 2000.0)
        assert len(fills) == 0

    def test_cancel_limit_order(self):
        order = self.sim.submit_limit_order(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.5,
            limit_price=48000.0,
        )
        assert self.sim.cancel_order(order.order_id)
        assert order.status == OrderStatus.CANCELLED
        # Should not fill anymore
        fills = self.sim.check_limit_orders("BTC-USD", 47000.0)
        assert len(fills) == 0

    def test_cancel_nonexistent_order(self):
        assert not self.sim.cancel_order("nonexistent-id")

    def test_limit_order_invalid_quantity(self):
        with pytest.raises(ValueError, match="quantity must be positive"):
            self.sim.submit_limit_order(
                symbol="BTC-USD",
                side=OrderSide.BUY,
                quantity=-1.0,
                limit_price=48000.0,
            )

    def test_limit_order_invalid_price(self):
        with pytest.raises(ValueError, match="limit_price must be positive"):
            self.sim.submit_limit_order(
                symbol="BTC-USD",
                side=OrderSide.BUY,
                quantity=1.0,
                limit_price=0.0,
            )


class TestPositionTracking:
    def setup_method(self):
        self.config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.0, taker_fee_rate=0.0),
        )
        self.sim = OrderSimulator(self.config)

    def test_single_buy_creates_position(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 0.5, 50000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos is not None
        assert pos.quantity == 0.5
        assert pos.avg_entry_price == 50000.0

    def test_two_buys_average_price(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 0.5, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 0.5, 52000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos.quantity == 1.0
        assert pos.avg_entry_price == 51000.0  # (50000*0.5 + 52000*0.5) / 1.0

    def test_buy_then_sell_realizes_pnl(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 55000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos.quantity == 0.0
        assert pos.realized_pnl == 5000.0  # (55000 - 50000) * 1.0

    def test_sell_then_buy_short_pnl(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 45000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos.quantity == 0.0
        assert pos.realized_pnl == 5000.0  # (50000 - 45000) * 1.0

    def test_partial_close(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 0.5, 55000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos.quantity == 0.5
        assert pos.realized_pnl == 2500.0  # (55000 - 50000) * 0.5
        assert pos.avg_entry_price == 50000.0

    def test_multiple_symbols(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("ETH-USD", OrderSide.BUY, 10.0, 3000.0)
        positions = self.sim.get_all_positions()
        assert len(positions) == 2
        assert positions["BTC-USD"].quantity == 1.0
        assert positions["ETH-USD"].quantity == 10.0

    def test_losing_trade_pnl(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 45000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos.realized_pnl == -5000.0


class TestFeeIntegration:
    def setup_method(self):
        self.config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002),
        )
        self.sim = OrderSimulator(self.config)

    def test_market_order_charged_taker_fee(self):
        fill = self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        assert fill.fee == 100.0  # 50000 * 0.002

    def test_limit_order_charged_maker_fee(self):
        self.sim.submit_limit_order("BTC-USD", OrderSide.BUY, 1.0, 48000.0)
        fills = self.sim.check_limit_orders("BTC-USD", 47000.0)
        assert fills[0].fee == 48.0  # 48000 * 0.001

    def test_fees_tracked_in_position(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 55000.0)
        pos = self.sim.get_position("BTC-USD")
        assert pos.total_fees == 210.0  # 100 + 110

    def test_net_cost_buy(self):
        fill = self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        assert fill.net_cost == 50100.0  # 50000 + 100

    def test_net_cost_sell(self):
        fill = self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 50000.0)
        assert fill.net_cost == 49900.0  # 50000 - 100


class TestFillReports:
    def setup_method(self):
        self.config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.0, taker_fee_rate=0.0),
        )
        self.sim = OrderSimulator(self.config)

    def test_empty_fill_report(self):
        report = self.sim.get_fill_report()
        assert report["total_fills"] == 0
        assert report["total_volume"] == 0.0

    def test_fill_report_after_trades(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 0.5, 55000.0)

        report = self.sim.get_fill_report()
        assert report["total_fills"] == 2
        assert report["total_volume"] == 77500.0  # 50000 + 27500

    def test_fill_report_filtered_by_symbol(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("ETH-USD", OrderSide.BUY, 10.0, 3000.0)

        btc_report = self.sim.get_fill_report(symbol="BTC-USD")
        assert btc_report["total_fills"] == 1

        eth_report = self.sim.get_fill_report(symbol="ETH-USD")
        assert eth_report["total_fills"] == 1

    def test_fill_report_has_fill_details(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        report = self.sim.get_fill_report()
        assert len(report["fills"]) == 1
        assert report["fills"][0]["symbol"] == "BTC-USD"
        assert report["fills"][0]["fill_price"] == 50000.0


class TestPnlSummary:
    def setup_method(self):
        self.config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.0, taker_fee_rate=0.001),
        )
        self.sim = OrderSimulator(self.config)

    def test_pnl_summary_empty(self):
        summary = self.sim.get_pnl_summary()
        assert summary["total_realized_pnl"] == 0.0
        assert summary["total_fees"] == 0.0
        assert summary["net_pnl"] == 0.0

    def test_pnl_summary_with_trades(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        self.sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 55000.0)
        summary = self.sim.get_pnl_summary()
        assert summary["total_realized_pnl"] == 5000.0
        total_fees = 50.0 + 55.0  # 50000*0.001 + 55000*0.001
        assert summary["total_fees"] == total_fees
        assert summary["net_pnl"] == 5000.0 - total_fees

    def test_pnl_summary_includes_positions(self):
        self.sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        summary = self.sim.get_pnl_summary()
        assert "BTC-USD" in summary["positions"]
        assert summary["positions"]["BTC-USD"]["quantity"] == 1.0


class TestGetPendingOrders:
    def setup_method(self):
        self.sim = OrderSimulator()

    def test_get_pending_orders(self):
        self.sim.submit_limit_order("BTC-USD", OrderSide.BUY, 1.0, 48000.0)
        self.sim.submit_limit_order("ETH-USD", OrderSide.BUY, 10.0, 2800.0)
        pending = self.sim.get_pending_orders()
        assert len(pending) == 2

    def test_get_pending_orders_by_symbol(self):
        self.sim.submit_limit_order("BTC-USD", OrderSide.BUY, 1.0, 48000.0)
        self.sim.submit_limit_order("ETH-USD", OrderSide.BUY, 10.0, 2800.0)
        pending = self.sim.get_pending_orders(symbol="BTC-USD")
        assert len(pending) == 1
        assert pending[0].symbol == "BTC-USD"


class TestReset:
    def test_reset_clears_all_state(self):
        sim = OrderSimulator()
        sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        sim.submit_limit_order("ETH-USD", OrderSide.BUY, 10.0, 2800.0)
        sim.reset()
        assert sim.get_all_positions() == {}
        assert sim.get_fills() == []
        assert sim.get_pending_orders() == []


class TestConfigYaml:
    def test_load_config_from_string(self):
        yaml_str = """
order_simulator:
  slippage:
    model: FIXED
    value: 5.0
    randomize: false
  fees:
    maker_fee_rate: 0.0005
    taker_fee_rate: 0.001
    min_fee: 0.50
"""
        config = load_config_from_string(yaml_str)
        assert config.slippage.model == SlippageModel.FIXED
        assert config.slippage.value == 5.0
        assert config.slippage.randomize is False
        assert config.fees.maker_fee_rate == 0.0005
        assert config.fees.taker_fee_rate == 0.001
        assert config.fees.min_fee == 0.50

    def test_load_config_from_file(self):
        yaml_content = """
order_simulator:
  slippage:
    model: PERCENTAGE
    value: 0.005
    randomize: true
  fees:
    maker_fee_rate: 0.001
    taker_fee_rate: 0.002
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(f.name)
        os.unlink(f.name)

        assert config.slippage.value == 0.005
        assert config.fees.taker_fee_rate == 0.002

    def test_default_config(self):
        config = default_config()
        assert config.slippage.model == SlippageModel.PERCENTAGE
        assert config.slippage.value == 0.001
        assert config.fees.maker_fee_rate == 0.001
        assert config.fees.taker_fee_rate == 0.002


class TestSlippageWithMarketOrders:
    """End-to-end tests combining slippage and fees in realistic scenarios."""

    def test_high_slippage_volatile_market(self):
        config = SimulatorConfig(
            slippage=SlippageConfig(
                model=SlippageModel.PERCENTAGE, value=0.05, randomize=False
            ),
            fees=FeeSchedule(taker_fee_rate=0.003),
        )
        sim = OrderSimulator(config)

        fill = sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        # 5% slippage: 50000 * 1.05 = 52500
        assert fill.fill_price == 52500.0
        # Fee on 52500: 52500 * 0.003 = 157.5
        assert fill.fee == 157.5

    def test_zero_fee_zero_slippage(self):
        config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.0, taker_fee_rate=0.0),
        )
        sim = OrderSimulator(config)

        fill = sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        assert fill.fill_price == 50000.0
        assert fill.fee == 0.0
        assert fill.net_cost == 50000.0

    def test_round_trip_pnl_with_fees_and_slippage(self):
        config = SimulatorConfig(
            slippage=SlippageConfig(
                model=SlippageModel.PERCENTAGE, value=0.001, randomize=False
            ),
            fees=FeeSchedule(taker_fee_rate=0.002),
        )
        sim = OrderSimulator(config)

        # Buy at 50000 with 0.1% slippage = 50050
        sim.submit_market_order("BTC-USD", OrderSide.BUY, 1.0, 50000.0)
        # Sell at 55000 with 0.1% slippage = 54945
        sim.submit_market_order("BTC-USD", OrderSide.SELL, 1.0, 55000.0)

        pos = sim.get_position("BTC-USD")
        # Realized PNL = 54945 - 50050 = 4895
        assert pos.realized_pnl == 4895.0
        # Fees: 50050*0.002 + 54945*0.002 = 100.1 + 109.89 = 209.99
        assert abs(pos.total_fees - 209.99) < 0.01

    def test_multiple_limit_orders_fill_in_order(self):
        config = SimulatorConfig(
            slippage=SlippageConfig(value=0.0),
            fees=FeeSchedule(maker_fee_rate=0.001, taker_fee_rate=0.002),
        )
        sim = OrderSimulator(config)

        sim.submit_limit_order("BTC-USD", OrderSide.BUY, 0.5, 49000.0)
        sim.submit_limit_order("BTC-USD", OrderSide.BUY, 0.5, 48000.0)

        # Only the first should fill
        fills = sim.check_limit_orders("BTC-USD", 48500.0)
        assert len(fills) == 1
        assert fills[0].fill_price == 49000.0

        # Now both remaining should fill
        fills = sim.check_limit_orders("BTC-USD", 47000.0)
        assert len(fills) == 1
        assert fills[0].fill_price == 48000.0


class TestFillDataclass:
    def test_fill_to_dict(self):
        fill = Fill(
            fill_id="f-1",
            order_id="o-1",
            symbol="BTC-USD",
            side="BUY",
            fill_price=50000.0,
            quantity=1.0,
            fee=100.0,
            slippage=50.0,
            notional=50000.0,
            net_cost=50100.0,
        )
        d = fill.to_dict()
        assert d["fill_id"] == "f-1"
        assert d["symbol"] == "BTC-USD"
        assert "timestamp" in d


class TestPositionDataclass:
    def test_position_to_dict(self):
        pos = Position(
            symbol="BTC-USD",
            quantity=1.0,
            avg_entry_price=50000.0,
            realized_pnl=1000.0,
            total_fees=50.0,
        )
        d = pos.to_dict()
        assert d["symbol"] == "BTC-USD"
        assert d["realized_pnl"] == 1000.0

    def test_notional_value(self):
        pos = Position(symbol="BTC-USD", quantity=2.0, avg_entry_price=50000.0)
        assert pos.notional_value == 100000.0
