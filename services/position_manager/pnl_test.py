"""Tests for PnL calculations and stop-loss/take-profit triggers."""

import pytest

from services.position_manager.models import Position, Side
from services.position_manager.pnl import (
    realized_pnl,
    should_stop_loss,
    should_take_profit,
    unrealized_pnl,
)


def _long_position(**overrides):
    defaults = dict(symbol="BTC/USD", side=Side.LONG, entry_price=50_000, quantity=1.0)
    defaults.update(overrides)
    return Position(**defaults)


def _short_position(**overrides):
    defaults = dict(symbol="BTC/USD", side=Side.SHORT, entry_price=50_000, quantity=1.0)
    defaults.update(overrides)
    return Position(**defaults)


class TestUnrealizedPnl:
    def test_long_profit(self):
        pos = _long_position()
        assert unrealized_pnl(pos, 55_000) == pytest.approx(5_000)

    def test_long_loss(self):
        pos = _long_position()
        assert unrealized_pnl(pos, 48_000) == pytest.approx(-2_000)

    def test_short_profit(self):
        pos = _short_position()
        assert unrealized_pnl(pos, 45_000) == pytest.approx(5_000)

    def test_short_loss(self):
        pos = _short_position()
        assert unrealized_pnl(pos, 52_000) == pytest.approx(-2_000)

    def test_flat(self):
        pos = _long_position()
        assert unrealized_pnl(pos, 50_000) == pytest.approx(0.0)

    def test_fractional_quantity(self):
        pos = _long_position(quantity=0.5)
        assert unrealized_pnl(pos, 52_000) == pytest.approx(1_000)


class TestRealizedPnl:
    def test_long_closed_profit(self):
        pos = _long_position()
        assert realized_pnl(pos, 60_000) == pytest.approx(10_000)

    def test_short_closed_profit(self):
        pos = _short_position()
        assert realized_pnl(pos, 40_000) == pytest.approx(10_000)

    def test_long_closed_loss(self):
        pos = _long_position()
        assert realized_pnl(pos, 45_000) == pytest.approx(-5_000)


class TestStopLoss:
    def test_long_stop_triggered(self):
        pos = _long_position(stop_loss=48_000)
        assert should_stop_loss(pos, 47_999) is True

    def test_long_stop_exact(self):
        pos = _long_position(stop_loss=48_000)
        assert should_stop_loss(pos, 48_000) is True

    def test_long_stop_not_triggered(self):
        pos = _long_position(stop_loss=48_000)
        assert should_stop_loss(pos, 49_000) is False

    def test_short_stop_triggered(self):
        pos = _short_position(stop_loss=52_000)
        assert should_stop_loss(pos, 52_001) is True

    def test_no_stop_loss_set(self):
        pos = _long_position()
        assert should_stop_loss(pos, 0) is False


class TestTakeProfit:
    def test_long_tp_triggered(self):
        pos = _long_position(take_profit=55_000)
        assert should_take_profit(pos, 55_001) is True

    def test_long_tp_exact(self):
        pos = _long_position(take_profit=55_000)
        assert should_take_profit(pos, 55_000) is True

    def test_long_tp_not_triggered(self):
        pos = _long_position(take_profit=55_000)
        assert should_take_profit(pos, 54_000) is False

    def test_short_tp_triggered(self):
        pos = _short_position(take_profit=45_000)
        assert should_take_profit(pos, 44_999) is True

    def test_no_take_profit_set(self):
        pos = _long_position()
        assert should_take_profit(pos, 999_999) is False
