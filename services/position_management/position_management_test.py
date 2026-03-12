"""Tests for position management models and lifecycle logic."""

import pytest

from services.position_management.position_management import (
    ManagedPosition,
    PositionSide,
    PositionStatus,
    PositionSummary,
    calculate_realized_pnl,
    calculate_unrealized_pnl,
    classify_asset_class,
    close_position,
    determine_status,
    mark_to_market,
    summarize_positions,
)


def _make_position(**overrides) -> ManagedPosition:
    defaults = {
        "id": "pos-1",
        "symbol": "BTC-USD",
        "side": PositionSide.LONG,
        "quantity": 1.0,
        "filled_quantity": 1.0,
        "entry_price": 40000.0,
        "current_price": 40000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "status": PositionStatus.FILLED,
        "strategy_name": "MACD_CROSSOVER",
        "asset_class": "Crypto",
        "opened_at": "2026-03-10T00:00:00+00:00",
        "updated_at": "2026-03-10T00:00:00+00:00",
    }
    defaults.update(overrides)
    return ManagedPosition(**defaults)


class TestCalculateUnrealizedPnl:
    def test_long_profit(self):
        pnl = calculate_unrealized_pnl(PositionSide.LONG, 0.1, 40000.0, 42000.0)
        assert pnl == 200.0

    def test_long_loss(self):
        pnl = calculate_unrealized_pnl(PositionSide.LONG, 0.1, 40000.0, 38000.0)
        assert pnl == -200.0

    def test_short_profit(self):
        pnl = calculate_unrealized_pnl(PositionSide.SHORT, 5.0, 100.0, 95.0)
        assert pnl == 25.0

    def test_short_loss(self):
        pnl = calculate_unrealized_pnl(PositionSide.SHORT, 5.0, 100.0, 105.0)
        assert pnl == -25.0

    def test_no_change(self):
        pnl = calculate_unrealized_pnl(PositionSide.LONG, 1.0, 100.0, 100.0)
        assert pnl == 0.0


class TestCalculateRealizedPnl:
    def test_long_profit(self):
        pnl = calculate_realized_pnl(PositionSide.LONG, 0.5, 40000.0, 44000.0)
        assert pnl == 2000.0

    def test_short_profit(self):
        pnl = calculate_realized_pnl(PositionSide.SHORT, 10.0, 100.0, 90.0)
        assert pnl == 100.0

    def test_long_loss(self):
        pnl = calculate_realized_pnl(PositionSide.LONG, 1.0, 100.0, 80.0)
        assert pnl == -20.0


class TestDetermineStatus:
    def test_open(self):
        assert determine_status(0.0, 1.0, 0.0) == PositionStatus.OPEN

    def test_partial_fill(self):
        assert determine_status(0.5, 1.0, 0.0) == PositionStatus.PARTIAL_FILL

    def test_filled(self):
        assert determine_status(1.0, 1.0, 0.0) == PositionStatus.FILLED

    def test_partially_closed(self):
        assert determine_status(1.0, 1.0, 0.5) == PositionStatus.PARTIALLY_CLOSED

    def test_closed(self):
        assert determine_status(1.0, 1.0, 1.0) == PositionStatus.CLOSED


class TestMarkToMarket:
    def test_updates_price_and_pnl(self):
        pos = _make_position()
        updated = mark_to_market(pos, 42000.0)

        assert updated.current_price == 42000.0
        assert updated.unrealized_pnl == 2000.0
        assert updated.id == pos.id
        assert updated.entry_price == pos.entry_price
        assert updated.updated_at != pos.updated_at

    def test_short_position(self):
        pos = _make_position(side=PositionSide.SHORT, entry_price=100.0)
        updated = mark_to_market(pos, 95.0)

        assert updated.unrealized_pnl == 5.0

    def test_preserves_metadata(self):
        pos = _make_position(
            strategy_name="SMA_RSI",
            signal_id="sig-1",
            stop_loss=39000.0,
            take_profit=45000.0,
            tags={"reason": "breakout"},
        )
        updated = mark_to_market(pos, 41000.0)

        assert updated.strategy_name == "SMA_RSI"
        assert updated.signal_id == "sig-1"
        assert updated.stop_loss == 39000.0
        assert updated.take_profit == 45000.0
        assert updated.tags == {"reason": "breakout"}


class TestClosePosition:
    def test_full_close(self):
        pos = _make_position(entry_price=40000.0, current_price=42000.0)
        closed = close_position(pos, exit_price=42000.0)

        assert closed.status == PositionStatus.CLOSED
        assert closed.filled_quantity == 0.0
        assert closed.realized_pnl == 2000.0
        assert closed.unrealized_pnl == 0.0
        assert closed.closed_at is not None
        assert closed.exit_price == 42000.0

    def test_partial_close(self):
        pos = _make_position(
            quantity=2.0,
            filled_quantity=2.0,
            entry_price=100.0,
            current_price=110.0,
        )
        result = close_position(pos, exit_price=110.0, close_quantity=1.0)

        assert result.status == PositionStatus.PARTIALLY_CLOSED
        assert result.filled_quantity == 1.0
        assert result.realized_pnl == 10.0
        assert result.unrealized_pnl == 10.0
        assert result.closed_at is None  # not fully closed

    def test_close_short_position(self):
        pos = _make_position(
            side=PositionSide.SHORT,
            entry_price=100.0,
            current_price=95.0,
        )
        closed = close_position(pos, exit_price=95.0)

        assert closed.realized_pnl == 5.0
        assert closed.status == PositionStatus.CLOSED

    def test_close_more_than_available(self):
        pos = _make_position(filled_quantity=0.5)
        closed = close_position(pos, exit_price=42000.0, close_quantity=5.0)

        # Should clamp to available quantity
        assert closed.filled_quantity == 0.5  # 1.0 - 0.5
        assert closed.status == PositionStatus.PARTIALLY_CLOSED

    def test_accumulated_realized_pnl(self):
        pos = _make_position(
            quantity=2.0,
            filled_quantity=2.0,
            entry_price=100.0,
            realized_pnl=50.0,  # already some realized
        )
        closed = close_position(pos, exit_price=110.0, close_quantity=1.0)

        assert closed.realized_pnl == 60.0  # 50 + 10


class TestClassifyAssetClass:
    def test_crypto(self):
        assert classify_asset_class("BTC-USD") == "Crypto"
        assert classify_asset_class("ETH/USD") == "Crypto"
        assert classify_asset_class("SOL-USD") == "Crypto"

    def test_other(self):
        assert classify_asset_class("AAPL") == "Other"
        assert classify_asset_class("UNKNOWN-USD") == "Other"


class TestSummarizePositions:
    def test_by_strategy(self):
        positions = [
            _make_position(
                id="p1",
                strategy_name="MACD",
                unrealized_pnl=100.0,
                realized_pnl=50.0,
                current_price=41000.0,
            ),
            _make_position(
                id="p2",
                strategy_name="MACD",
                status=PositionStatus.CLOSED,
                unrealized_pnl=0.0,
                realized_pnl=200.0,
                filled_quantity=0.0,
            ),
            _make_position(
                id="p3",
                strategy_name="SMA_RSI",
                unrealized_pnl=30.0,
                realized_pnl=0.0,
                current_price=2100.0,
            ),
        ]

        summaries = summarize_positions(positions, group_by="strategy")
        assert len(summaries) == 2

        macd = next(s for s in summaries if s.group_key == "MACD")
        assert macd.num_open == 1
        assert macd.num_closed == 1
        assert macd.total_unrealized_pnl == 100.0
        assert macd.total_realized_pnl == 250.0  # 50 + 200

        sma = next(s for s in summaries if s.group_key == "SMA_RSI")
        assert sma.num_open == 1
        assert sma.num_closed == 0

    def test_by_asset_class(self):
        positions = [
            _make_position(id="p1", asset_class="Crypto", unrealized_pnl=100.0),
            _make_position(id="p2", asset_class="Other", unrealized_pnl=50.0),
        ]

        summaries = summarize_positions(positions, group_by="asset_class")
        assert len(summaries) == 2
        assert summaries[0].group_key == "Crypto"
        assert summaries[1].group_key == "Other"

    def test_empty_positions(self):
        assert summarize_positions([]) == []

    def test_unknown_strategy(self):
        pos = _make_position(strategy_name=None, unrealized_pnl=10.0)
        summaries = summarize_positions([pos], group_by="strategy")
        assert summaries[0].group_key == "unknown"
