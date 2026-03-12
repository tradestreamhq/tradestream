"""Tests for the signal replay service."""

import pytest

from services.signal_replay.models import (
    HistoricalSignal,
    ReplayConfig,
    ReplayDecision,
    SignalAction,
)
from services.signal_replay.replayer import SignalReplayer


@pytest.fixture
def config():
    """Default replay config for tests."""
    return ReplayConfig(
        strategy_name="SMA_RSI",
        symbol="BTC-USD",
        position_size=1.0,
    )


@pytest.fixture
def buy_signal():
    return HistoricalSignal(
        timestamp_ms=1000,
        symbol="BTC-USD",
        strategy_name="SMA_RSI",
        action=SignalAction.BUY,
        price=100.0,
        confidence=0.8,
    )


@pytest.fixture
def sell_signal():
    return HistoricalSignal(
        timestamp_ms=2000,
        symbol="BTC-USD",
        strategy_name="SMA_RSI",
        action=SignalAction.SELL,
        price=110.0,
        confidence=0.9,
    )


@pytest.fixture
def hold_signal():
    return HistoricalSignal(
        timestamp_ms=1500,
        symbol="BTC-USD",
        strategy_name="SMA_RSI",
        action=SignalAction.HOLD,
        price=105.0,
    )


@pytest.fixture
def stop_loss_signal():
    return HistoricalSignal(
        timestamp_ms=2000,
        symbol="BTC-USD",
        strategy_name="SMA_RSI",
        action=SignalAction.STOP_LOSS,
        price=90.0,
    )


class TestSignalFiltering:
    """Tests for signal filtering and sorting."""

    def test_filters_by_symbol(self, config):
        signals = [
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "ETH-USD", "SMA_RSI", SignalAction.BUY, 50.0),
        ]
        replayer = SignalReplayer(config, signals)
        assert len(replayer.signals) == 1
        assert replayer.signals[0].symbol == "BTC-USD"

    def test_filters_by_strategy(self, config):
        signals = [
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "BTC-USD", "MACD", SignalAction.BUY, 100.0),
        ]
        replayer = SignalReplayer(config, signals)
        assert len(replayer.signals) == 1
        assert replayer.signals[0].strategy_name == "SMA_RSI"

    def test_filters_by_date_range(self):
        config = ReplayConfig(
            strategy_name="SMA_RSI",
            symbol="BTC-USD",
            start_timestamp_ms=1500,
            end_timestamp_ms=2500,
        )
        signals = [
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 110.0),
            HistoricalSignal(3000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 120.0),
        ]
        replayer = SignalReplayer(config, signals)
        assert len(replayer.signals) == 1
        assert replayer.signals[0].timestamp_ms == 2000

    def test_sorts_by_timestamp(self, config):
        signals = [
            HistoricalSignal(3000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 120.0),
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "BTC-USD", "SMA_RSI", SignalAction.HOLD, 110.0),
        ]
        replayer = SignalReplayer(config, signals)
        timestamps = [s.timestamp_ms for s in replayer.signals]
        assert timestamps == [1000, 2000, 3000]

    def test_empty_signals(self, config):
        replayer = SignalReplayer(config, [])
        assert replayer.is_complete
        result = replayer.replay_all()
        assert result.total_signals == 0
        assert result.total_pnl == 0.0


class TestStepMode:
    """Tests for step-through replay mode."""

    def test_step_returns_entry(self, config, buy_signal):
        replayer = SignalReplayer(config, [buy_signal])
        entry = replayer.step()
        assert entry is not None
        assert entry.step == 0
        assert entry.signal == buy_signal
        assert entry.decision == ReplayDecision.ENTER_LONG

    def test_step_returns_none_when_complete(self, config):
        replayer = SignalReplayer(config, [])
        assert replayer.step() is None

    def test_step_through_generator(self, config, buy_signal, sell_signal):
        replayer = SignalReplayer(config, [buy_signal, sell_signal])
        entries = list(replayer.step_through())
        assert len(entries) == 2
        assert entries[0].decision == ReplayDecision.ENTER_LONG
        assert entries[1].decision == ReplayDecision.EXIT_LONG

    def test_state_transitions(self, config, buy_signal, sell_signal):
        replayer = SignalReplayer(config, [buy_signal, sell_signal])

        entry1 = replayer.step()
        assert entry1.state_before.position == "FLAT"
        assert entry1.state_after.position == "LONG"
        assert entry1.state_after.entry_price == 100.0

        entry2 = replayer.step()
        assert entry2.state_before.position == "LONG"
        assert entry2.state_after.position == "FLAT"

    def test_is_complete_tracking(self, config, buy_signal):
        replayer = SignalReplayer(config, [buy_signal])
        assert not replayer.is_complete
        replayer.step()
        assert replayer.is_complete


class TestDecisionLogic:
    """Tests for strategy decision evaluation."""

    def test_buy_when_flat_enters_long(self, config, buy_signal):
        replayer = SignalReplayer(config, [buy_signal])
        entry = replayer.step()
        assert entry.decision == ReplayDecision.ENTER_LONG

    def test_buy_when_long_holds(self, config, buy_signal):
        second_buy = HistoricalSignal(2000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 110.0)
        replayer = SignalReplayer(config, [buy_signal, second_buy])
        replayer.step()
        entry = replayer.step()
        assert entry.decision == ReplayDecision.HOLD

    def test_sell_when_long_exits(self, config, buy_signal, sell_signal):
        replayer = SignalReplayer(config, [buy_signal, sell_signal])
        replayer.step()
        entry = replayer.step()
        assert entry.decision == ReplayDecision.EXIT_LONG

    def test_sell_when_flat_skips(self, config, sell_signal):
        replayer = SignalReplayer(config, [sell_signal])
        entry = replayer.step()
        assert entry.decision == ReplayDecision.SKIP

    def test_stop_loss_when_long(self, config, buy_signal, stop_loss_signal):
        replayer = SignalReplayer(config, [buy_signal, stop_loss_signal])
        replayer.step()
        entry = replayer.step()
        assert entry.decision == ReplayDecision.STOP_OUT

    def test_hold_signal(self, config, hold_signal):
        replayer = SignalReplayer(config, [hold_signal])
        entry = replayer.step()
        assert entry.decision == ReplayDecision.HOLD


class TestPnLCalculation:
    """Tests for profit and loss calculations."""

    def test_winning_trade_pnl(self, config, buy_signal, sell_signal):
        replayer = SignalReplayer(config, [buy_signal, sell_signal])
        result = replayer.replay_all()
        assert result.total_pnl == pytest.approx(10.0)  # 110 - 100
        assert result.win_count == 1
        assert result.loss_count == 0
        assert result.total_trades == 1

    def test_losing_trade_pnl(self, config, buy_signal, stop_loss_signal):
        replayer = SignalReplayer(config, [buy_signal, stop_loss_signal])
        result = replayer.replay_all()
        assert result.total_pnl == pytest.approx(-10.0)  # 90 - 100
        assert result.win_count == 0
        assert result.loss_count == 1

    def test_unrealized_pnl_while_in_position(self, config, buy_signal, hold_signal):
        replayer = SignalReplayer(config, [buy_signal, hold_signal])
        replayer.step()
        entry = replayer.step()
        assert entry.state_after.unrealized_pnl == pytest.approx(5.0)  # 105 - 100
        assert entry.state_after.realized_pnl == 0.0

    def test_position_size_affects_pnl(self):
        config = ReplayConfig(
            strategy_name="SMA_RSI",
            symbol="BTC-USD",
            position_size=2.5,
        )
        signals = [
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 110.0),
        ]
        replayer = SignalReplayer(config, signals)
        result = replayer.replay_all()
        assert result.total_pnl == pytest.approx(25.0)  # (110-100) * 2.5

    def test_multiple_round_trips(self, config):
        signals = [
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 110.0),
            HistoricalSignal(3000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 105.0),
            HistoricalSignal(4000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 115.0),
        ]
        replayer = SignalReplayer(config, signals)
        result = replayer.replay_all()
        assert result.total_pnl == pytest.approx(20.0)  # 10 + 10
        assert result.total_trades == 2
        assert result.win_count == 2


class TestBatchMode:
    """Tests for batch replay mode."""

    def test_replay_all_returns_result(self, config, buy_signal, sell_signal):
        replayer = SignalReplayer(config, [buy_signal, sell_signal])
        result = replayer.replay_all()
        assert result.strategy_name == "SMA_RSI"
        assert result.symbol == "BTC-USD"
        assert result.total_signals == 2
        assert len(result.decision_log) == 2

    def test_win_rate(self, config):
        signals = [
            HistoricalSignal(1000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 100.0),
            HistoricalSignal(2000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 110.0),
            HistoricalSignal(3000, "BTC-USD", "SMA_RSI", SignalAction.BUY, 105.0),
            HistoricalSignal(4000, "BTC-USD", "SMA_RSI", SignalAction.SELL, 100.0),
        ]
        replayer = SignalReplayer(config, signals)
        result = replayer.replay_all()
        assert result.win_rate == pytest.approx(0.5)

    def test_win_rate_no_trades(self, config):
        replayer = SignalReplayer(config, [])
        result = replayer.replay_all()
        assert result.win_rate == 0.0

    def test_decision_log_preserved(self, config, buy_signal, sell_signal):
        replayer = SignalReplayer(config, [buy_signal, sell_signal])
        result = replayer.replay_all()
        assert replayer.decision_log == result.decision_log
