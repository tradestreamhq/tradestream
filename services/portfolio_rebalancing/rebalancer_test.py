"""Tests for the portfolio rebalancing engine."""

import pytest

from services.portfolio_rebalancing.rebalancer import (
    AllocationTarget,
    CurrentHolding,
    RebalanceConstraints,
    RebalanceTrade,
    TradeSide,
    compute_current_allocation,
    compute_drift,
    compute_rebalance_trades,
    format_rebalance_report,
)


class TestComputeCurrentAllocation:
    def test_single_holding(self):
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
        ]
        equity, alloc = compute_current_allocation(holdings, cash=5000.0)
        assert equity == 10000.0
        assert alloc["BTC-USD"] == pytest.approx(0.5)

    def test_multiple_holdings(self):
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
            CurrentHolding("ETH-USD", 2.0, 2500.0, 5000.0),
        ]
        equity, alloc = compute_current_allocation(holdings, cash=0.0)
        assert equity == 10000.0
        assert alloc["BTC-USD"] == pytest.approx(0.5)
        assert alloc["ETH-USD"] == pytest.approx(0.5)

    def test_empty_portfolio(self):
        equity, alloc = compute_current_allocation([], cash=10000.0)
        assert equity == 10000.0
        assert alloc == {}

    def test_zero_equity(self):
        equity, alloc = compute_current_allocation([], cash=0.0)
        assert equity == 0.0
        assert alloc == {}

    def test_cash_only(self):
        equity, alloc = compute_current_allocation([], cash=5000.0)
        assert equity == 5000.0
        assert alloc == {}


class TestComputeDrift:
    def test_under_allocated(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        current = {"BTC-USD": 0.3}
        drift = compute_drift(targets, current)
        assert drift["BTC-USD"] == pytest.approx(0.2)

    def test_over_allocated(self):
        targets = [AllocationTarget("BTC-USD", 0.3)]
        current = {"BTC-USD": 0.5}
        drift = compute_drift(targets, current)
        assert drift["BTC-USD"] == pytest.approx(-0.2)

    def test_on_target(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        current = {"BTC-USD": 0.5}
        drift = compute_drift(targets, current)
        assert drift["BTC-USD"] == pytest.approx(0.0)

    def test_new_target_not_held(self):
        targets = [AllocationTarget("SOL-USD", 0.2)]
        current = {}
        drift = compute_drift(targets, current)
        assert drift["SOL-USD"] == pytest.approx(0.2)

    def test_held_but_not_targeted(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        current = {"BTC-USD": 0.3, "DOGE-USD": 0.2}
        drift = compute_drift(targets, current)
        assert drift["DOGE-USD"] == pytest.approx(-0.2)

    def test_multiple_targets(self):
        targets = [
            AllocationTarget("BTC-USD", 0.4),
            AllocationTarget("ETH-USD", 0.3),
        ]
        current = {"BTC-USD": 0.5, "ETH-USD": 0.2}
        drift = compute_drift(targets, current)
        assert drift["BTC-USD"] == pytest.approx(-0.1)
        assert drift["ETH-USD"] == pytest.approx(0.1)


class TestComputeRebalanceTrades:
    def _make_constraints(self, **kwargs):
        defaults = {
            "min_trade_value": 1.0,
            "max_trade_pct": 0.5,
            "max_slippage_pct": 0.0,
            "drift_threshold_pct": 0.01,
        }
        defaults.update(kwargs)
        return RebalanceConstraints(**defaults)

    def test_buy_under_allocated_asset(self):
        targets = [
            AllocationTarget("BTC-USD", 0.5),
            AllocationTarget("ETH-USD", 0.5),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints()

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=5000.0,
            current_prices=prices,
            constraints=constraints,
        )

        assert report.total_equity == 10000.0
        buy_trades = [t for t in report.trades if t.side == TradeSide.BUY]
        assert len(buy_trades) >= 1
        eth_buys = [t for t in buy_trades if t.symbol == "ETH-USD"]
        assert len(eth_buys) == 1
        assert eth_buys[0].quantity > 0

    def test_sell_over_allocated_asset(self):
        targets = [
            AllocationTarget("BTC-USD", 0.3),
            AllocationTarget("ETH-USD", 0.3),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.2, 50000.0, 10000.0),
            CurrentHolding("ETH-USD", 1.0, 2500.0, 2500.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints()

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=0.0,
            current_prices=prices,
            constraints=constraints,
        )

        sell_trades = [t for t in report.trades if t.side == TradeSide.SELL]
        assert len(sell_trades) >= 1
        btc_sells = [t for t in sell_trades if t.symbol == "BTC-USD"]
        assert len(btc_sells) == 1

    def test_no_trades_when_on_target(self):
        targets = [
            AllocationTarget("BTC-USD", 0.5),
            AllocationTarget("ETH-USD", 0.5),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
            CurrentHolding("ETH-USD", 2.0, 2500.0, 5000.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints()

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=0.0,
            current_prices=prices,
            constraints=constraints,
        )

        assert len(report.trades) == 0

    def test_drift_threshold_filters_small_drifts(self):
        targets = [
            AllocationTarget("BTC-USD", 0.505),
            AllocationTarget("ETH-USD", 0.495),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
            CurrentHolding("ETH-USD", 2.0, 2500.0, 5000.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints(drift_threshold_pct=0.02)

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=0.0,
            current_prices=prices,
            constraints=constraints,
        )

        assert len(report.trades) == 0
        assert len(report.skipped) == 2

    def test_min_trade_value_filters_tiny_trades(self):
        targets = [
            AllocationTarget("BTC-USD", 0.48),
            AllocationTarget("ETH-USD", 0.52),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.001, 50000.0, 50.0),
            CurrentHolding("ETH-USD", 0.02, 2500.0, 50.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints(
            min_trade_value=100.0, drift_threshold_pct=0.01
        )

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=0.0,
            current_prices=prices,
            constraints=constraints,
        )

        # All computed trades should be >= min_trade_value
        for t in report.trades:
            assert t.estimated_value >= 100.0

    def test_max_trade_pct_caps_large_trades(self):
        targets = [AllocationTarget("BTC-USD", 1.0)]
        holdings = []
        prices = {"BTC-USD": 50000.0}
        constraints = self._make_constraints(max_trade_pct=0.1)

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=10000.0,
            current_prices=prices,
            constraints=constraints,
        )

        for t in report.trades:
            assert t.estimated_value <= 10000.0 * 0.1 + 1  # small float tolerance

    def test_insufficient_cash_reduces_buy(self):
        targets = [AllocationTarget("BTC-USD", 0.8)]
        holdings = [
            CurrentHolding("BTC-USD", 0.01, 50000.0, 500.0),
        ]
        prices = {"BTC-USD": 50000.0}
        constraints = self._make_constraints(max_trade_pct=1.0)

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=100.0,
            current_prices=prices,
            constraints=constraints,
        )

        buy_trades = [t for t in report.trades if t.side == TradeSide.BUY]
        if buy_trades:
            # Should not exceed available cash
            assert buy_trades[0].estimated_value <= 100.0

    def test_sell_frees_cash_for_buy(self):
        targets = [
            AllocationTarget("BTC-USD", 0.0),
            AllocationTarget("ETH-USD", 0.8),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints(max_trade_pct=1.0)

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=0.0,
            current_prices=prices,
            constraints=constraints,
        )

        sides = [t.side for t in report.trades]
        assert TradeSide.SELL in sides
        assert TradeSide.BUY in sides

    def test_empty_portfolio_with_cash(self):
        targets = [
            AllocationTarget("BTC-USD", 0.5),
            AllocationTarget("ETH-USD", 0.5),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints(max_trade_pct=1.0)

        report = compute_rebalance_trades(
            targets,
            [],
            cash=10000.0,
            current_prices=prices,
            constraints=constraints,
        )

        assert len(report.trades) == 2
        assert all(t.side == TradeSide.BUY for t in report.trades)

    def test_zero_equity_returns_empty_report(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        prices = {"BTC-USD": 50000.0}

        report = compute_rebalance_trades(
            targets,
            [],
            cash=0.0,
            current_prices=prices,
        )

        assert report.total_equity == 0.0
        assert len(report.trades) == 0

    def test_asset_held_but_not_targeted_is_sold(self):
        targets = [AllocationTarget("ETH-USD", 0.5)]
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = self._make_constraints(max_trade_pct=1.0)

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=5000.0,
            current_prices=prices,
            constraints=constraints,
        )

        btc_trades = [t for t in report.trades if t.symbol == "BTC-USD"]
        assert len(btc_trades) == 1
        assert btc_trades[0].side == TradeSide.SELL

    def test_missing_price_skips_symbol(self):
        targets = [AllocationTarget("XYZ-USD", 0.5)]
        constraints = self._make_constraints()

        report = compute_rebalance_trades(
            targets,
            [],
            cash=10000.0,
            current_prices={},
            constraints=constraints,
        )

        assert len(report.trades) == 0
        assert any(s["symbol"] == "XYZ-USD" for s in report.skipped)

    def test_slippage_cost_deducted_from_cash(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        prices = {"BTC-USD": 100.0}
        constraints = self._make_constraints(max_slippage_pct=0.01, max_trade_pct=1.0)

        report = compute_rebalance_trades(
            targets,
            [],
            cash=1000.0,
            current_prices=prices,
            constraints=constraints,
        )

        # Cash after should account for slippage
        assert report.cash_after_estimate < report.cash_before

    def test_report_metadata(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        holdings = [CurrentHolding("BTC-USD", 0.01, 50000.0, 500.0)]
        prices = {"BTC-USD": 50000.0}

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=500.0,
            current_prices=prices,
        )

        assert report.total_equity == 1000.0
        assert "BTC-USD" in report.target_allocation
        assert "BTC-USD" in report.current_allocation
        assert "BTC-USD" in report.drift
        assert report.cash_before == 500.0
        assert report.timestamp  # non-empty


class TestFormatRebalanceReport:
    def test_format_with_trades(self):
        targets = [
            AllocationTarget("BTC-USD", 0.6),
            AllocationTarget("ETH-USD", 0.4),
        ]
        holdings = [
            CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0),
        ]
        prices = {"BTC-USD": 50000.0, "ETH-USD": 2500.0}
        constraints = RebalanceConstraints(
            min_trade_value=1.0,
            drift_threshold_pct=0.01,
            max_trade_pct=1.0,
        )

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=5000.0,
            current_prices=prices,
            constraints=constraints,
        )
        text = format_rebalance_report(report)

        assert "PORTFOLIO REBALANCE REPORT" in text
        assert "Total Equity" in text
        assert "BTC-USD" in text
        assert "ETH-USD" in text
        assert "BUY" in text or "SELL" in text

    def test_format_no_trades(self):
        targets = [AllocationTarget("BTC-USD", 0.5)]
        holdings = [CurrentHolding("BTC-USD", 0.1, 50000.0, 5000.0)]
        prices = {"BTC-USD": 50000.0}
        constraints = RebalanceConstraints(drift_threshold_pct=0.01)

        report = compute_rebalance_trades(
            targets,
            holdings,
            cash=5000.0,
            current_prices=prices,
            constraints=constraints,
        )
        text = format_rebalance_report(report)

        assert "No trades needed" in text
