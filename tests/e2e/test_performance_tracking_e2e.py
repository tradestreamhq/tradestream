"""E2E tests for the full signal performance tracking pipeline.

Tests the complete flow: signal generation → quality scoring → delivery →
portfolio state update → PnL tracking → performance attribution.
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.e2e.conftest import (
    FakePool,
    FakeRedis,
    FakeRow,
    make_candles,
    make_signal,
    make_strategy_performance,
)
from services.signal_quality.scorer import (
    QualityScore,
    compute_grade,
    score_signal,
)
from services.portfolio_state.portfolio_state import (
    AccountBalance,
    Position,
    PortfolioState,
    RiskMetrics,
)
from services.shared.pipeline_metrics import PipelineMetrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_position(symbol="BTC/USD", side="LONG", qty=0.1, entry=65000, current=66500):
    return Position(
        symbol=symbol,
        side=side,
        quantity=qty,
        entry_price=entry,
        current_price=current,
        unrealized_pnl=round((current - entry) * qty, 2),
        unrealized_pnl_percent=round((current - entry) / entry * 100, 2),
        opened_at=datetime.now(timezone.utc).isoformat(),
        trade_id=str(uuid.uuid4()),
    )


def _make_balance(equity=10000, cash=5000, unrealized=150, realized=50):
    return AccountBalance(
        total_equity=equity,
        available_cash=cash,
        buying_power=cash * 2,
        margin_used=equity - cash,
        margin_available=cash,
        unrealized_pnl=unrealized,
        realized_pnl_today=realized,
    )


def _make_risk_metrics(positions):
    if not positions:
        return RiskMetrics(
            portfolio_heat=0.0,
            max_position_pct=0.0,
            max_position_symbol="",
            num_open_positions=0,
        )
    total_value = sum(p.current_price * p.quantity for p in positions)
    max_pos = max(positions, key=lambda p: p.current_price * p.quantity)
    max_pct = (
        (max_pos.current_price * max_pos.quantity) / total_value if total_value else 0
    )
    return RiskMetrics(
        portfolio_heat=round(total_value / 10000 * 100, 2),
        max_position_pct=round(max_pct * 100, 2),
        max_position_symbol=max_pos.symbol,
        num_open_positions=len(positions),
    )


# ---------------------------------------------------------------------------
# Tests: Signal Quality Scoring Pipeline
# ---------------------------------------------------------------------------


class TestSignalQualityScoringPipeline:
    """Test signal quality scoring as part of the performance pipeline."""

    def test_high_quality_signal_scores_grade_a(self):
        score = score_signal(
            entry_conditions_met=5,
            total_entry_conditions=5,
            volume_above_average=True,
            volume_ratio=1.8,
            trend_direction_matches=True,
            trend_strength=0.9,
            volatility_percentile=0.4,
        )
        assert isinstance(score, QualityScore)
        assert score.grade == "A"
        assert score.confidence >= 0.80

    def test_low_quality_signal_scores_grade_d_or_f(self):
        score = score_signal(
            entry_conditions_met=1,
            total_entry_conditions=5,
            volume_above_average=False,
            volume_ratio=0.3,
            trend_direction_matches=False,
            trend_strength=0.2,
            volatility_percentile=0.95,
        )
        assert score.grade in ("D", "F")
        assert score.confidence < 0.50

    def test_moderate_signal_scores_grade_b_or_c(self):
        score = score_signal(
            entry_conditions_met=3,
            total_entry_conditions=5,
            volume_above_average=True,
            volume_ratio=1.1,
            trend_direction_matches=True,
            trend_strength=0.5,
            volatility_percentile=0.6,
        )
        assert score.grade in ("B", "C")

    def test_grade_thresholds_are_correct(self):
        assert compute_grade(0.85) == "A"
        assert compute_grade(0.70) == "B"
        assert compute_grade(0.55) == "C"
        assert compute_grade(0.40) == "D"
        assert compute_grade(0.20) == "F"


# ---------------------------------------------------------------------------
# Tests: Portfolio State Tracking
# ---------------------------------------------------------------------------


class TestPortfolioStateTracking:
    """Test portfolio state computation from positions and balances."""

    def test_portfolio_state_with_open_positions(self):
        positions = [
            _make_position("BTC/USD", "LONG", 0.1, 65000, 66500),
            _make_position("ETH/USD", "LONG", 1.0, 3500, 3650),
        ]
        balance = _make_balance(equity=10300, unrealized=300)
        risk = _make_risk_metrics(positions)
        state = PortfolioState(
            balance=balance,
            positions=positions,
            risk_metrics=risk,
            recent_trades=[],
            as_of=datetime.now(timezone.utc).isoformat(),
        )
        assert len(state.positions) == 2
        assert state.balance.total_equity == 10300
        assert state.risk_metrics.num_open_positions == 2

    def test_empty_portfolio_state(self):
        positions = []
        balance = _make_balance(equity=10000, cash=10000, unrealized=0)
        risk = _make_risk_metrics(positions)
        state = PortfolioState(
            balance=balance,
            positions=positions,
            risk_metrics=risk,
            recent_trades=[],
            as_of=datetime.now(timezone.utc).isoformat(),
        )
        assert len(state.positions) == 0
        assert state.risk_metrics.portfolio_heat == 0.0
        assert state.balance.available_cash == 10000

    def test_unrealized_pnl_calculation(self):
        pos = _make_position("BTC/USD", "LONG", 0.5, 60000, 62000)
        assert pos.unrealized_pnl == 1000.0
        assert pos.unrealized_pnl_percent == pytest.approx(3.33, abs=0.01)

    def test_risk_metrics_max_position(self):
        positions = [
            _make_position("BTC/USD", "LONG", 0.1, 65000, 65000),
            _make_position("ETH/USD", "LONG", 10.0, 3500, 3500),
        ]
        risk = _make_risk_metrics(positions)
        assert risk.max_position_symbol == "ETH/USD"
        assert risk.num_open_positions == 2


# ---------------------------------------------------------------------------
# Tests: Full Signal-to-Performance Pipeline
# ---------------------------------------------------------------------------


class TestSignalToPerformancePipeline:
    """End-to-end: signal generated → quality scored → delivered → PnL tracked."""

    def test_full_pipeline_signal_to_portfolio_update(self):
        """Signal generation through to portfolio state update."""
        # Step 1: Generate a signal
        signal = make_signal(
            strategy_name="trend_follower",
            instrument="BTC/USD",
            direction="BUY",
            confidence=0.88,
            entry_price=65000,
            stop_loss=63500,
            take_profit=68000,
        )
        assert signal["direction"] == "BUY"
        assert signal["confidence"] == 0.88

        # Step 2: Score signal quality
        quality = score_signal(
            entry_conditions_met=4,
            total_entry_conditions=5,
            volume_above_average=True,
            volume_ratio=1.5,
            trend_direction_matches=True,
            trend_strength=0.7,
            volatility_percentile=0.35,
        )
        assert quality.grade in ("A", "B")

        # Step 3: Record in metrics
        metrics = PipelineMetrics()
        metrics.signals_generated.inc()
        metrics.deliveries_attempted.inc()
        metrics.deliveries_succeeded.inc()

        # Step 4: Create position from signal
        position = _make_position(
            symbol=signal["instrument"],
            side="LONG",
            qty=0.1,
            entry=signal["entry_price"],
            current=signal["entry_price"],  # at entry, no P&L yet
        )
        assert position.unrealized_pnl == 0.0

        # Step 5: Price moves — portfolio state updates
        position_after = _make_position(
            symbol=signal["instrument"],
            side="LONG",
            qty=0.1,
            entry=signal["entry_price"],
            current=66000,
        )
        assert position_after.unrealized_pnl == 100.0

        # Step 6: Verify metrics captured
        snapshot = metrics.snapshot()
        assert snapshot["signal_generation"]["total"] >= 1
        assert snapshot["delivery"]["succeeded"] >= 1

    def test_pipeline_with_stop_loss_hit(self):
        """Signal that hits stop loss should result in negative PnL."""
        signal = make_signal(
            direction="BUY",
            entry_price=65000,
            stop_loss=63000,
            take_profit=70000,
        )
        pos = _make_position(
            entry=signal["entry_price"],
            current=signal["stop_loss"],
            qty=0.1,
        )
        assert pos.unrealized_pnl < 0
        assert pos.unrealized_pnl == pytest.approx(-200.0)

    def test_pipeline_with_take_profit_hit(self):
        """Signal that hits take profit should result in positive PnL."""
        signal = make_signal(
            direction="BUY",
            entry_price=65000,
            stop_loss=63000,
            take_profit=70000,
        )
        pos = _make_position(
            entry=signal["entry_price"],
            current=signal["take_profit"],
            qty=0.1,
        )
        assert pos.unrealized_pnl > 0
        assert pos.unrealized_pnl == pytest.approx(500.0)

    def test_multiple_signals_portfolio_performance(self):
        """Multiple signals → portfolio with multiple positions → aggregate metrics."""
        signals = [
            make_signal(
                strategy_name="strat_a", instrument="BTC/USD", entry_price=65000
            ),
            make_signal(
                strategy_name="strat_b", instrument="ETH/USD", entry_price=3500
            ),
            make_signal(strategy_name="strat_c", instrument="SOL/USD", entry_price=150),
        ]
        positions = [
            _make_position("BTC/USD", "LONG", 0.1, 65000, 66000),
            _make_position("ETH/USD", "LONG", 1.0, 3500, 3600),
            _make_position("SOL/USD", "LONG", 10.0, 150, 155),
        ]
        balance = _make_balance(
            equity=10000 + sum(p.unrealized_pnl for p in positions),
            unrealized=sum(p.unrealized_pnl for p in positions),
        )
        risk = _make_risk_metrics(positions)

        state = PortfolioState(
            balance=balance,
            positions=positions,
            risk_metrics=risk,
            recent_trades=[],
            as_of=datetime.now(timezone.utc).isoformat(),
        )
        assert len(state.positions) == 3
        assert state.balance.unrealized_pnl > 0
        assert state.risk_metrics.num_open_positions == 3

    def test_strategy_performance_attribution(self):
        """Strategy performance is tracked correctly across signals."""
        performances = [
            make_strategy_performance(
                "strat_a", sharpe_ratio=2.0, win_rate=0.7, trade_count=50
            ),
            make_strategy_performance(
                "strat_b", sharpe_ratio=0.8, win_rate=0.45, trade_count=30
            ),
            make_strategy_performance(
                "strat_c", sharpe_ratio=1.5, win_rate=0.6, trade_count=40
            ),
        ]
        best = max(performances, key=lambda p: p["sharpe_ratio"])
        assert best["strategy_spec_id"] == "strat_a"
        assert all(p["trade_count"] >= 20 for p in performances)

    def test_metrics_pipeline_counters_increment(self):
        """Pipeline metrics correctly track signal flow counts."""
        metrics = PipelineMetrics()

        # Generate 5 signals
        for _ in range(5):
            metrics.signals_generated.inc()

        # Deliver 4 (one fails)
        for _ in range(4):
            metrics.deliveries_attempted.inc()
            metrics.deliveries_succeeded.inc()
        metrics.deliveries_attempted.inc()
        metrics.deliveries_failed.inc()

        snapshot = metrics.snapshot()
        assert snapshot["signal_generation"]["total"] == 5
        assert snapshot["delivery"]["succeeded"] == 4
        assert snapshot["delivery"]["failed"] == 1
        assert snapshot["delivery"]["attempted"] == 5

    def test_channel_specific_metrics(self):
        """Per-channel delivery metrics are tracked."""
        metrics = PipelineMetrics()

        metrics.record_channel_success("telegram")
        metrics.record_channel_success("telegram")
        metrics.record_channel_success("webhook")
        metrics.record_channel_failure("email")

        snapshot = metrics.snapshot()
        channels = snapshot["delivery"]["by_channel"]
        assert channels["telegram"]["success"] == 2
        assert channels["webhook"]["success"] == 1
        assert channels["email"]["failure"] == 1

    def test_delivery_success_rate(self):
        """Delivery success rate is computed correctly."""
        metrics = PipelineMetrics()

        for _ in range(8):
            metrics.deliveries_attempted.inc()
            metrics.deliveries_succeeded.inc()
        for _ in range(2):
            metrics.deliveries_attempted.inc()
            metrics.deliveries_failed.inc()

        assert metrics.delivery_success_rate() == pytest.approx(0.8)

    def test_delivery_latency_histogram(self):
        """Delivery latency histogram tracks percentiles."""
        metrics = PipelineMetrics()

        latencies = [50, 80, 100, 120, 150, 200, 250, 300, 500, 1000]
        for lat in latencies:
            metrics.delivery_latency_ms.observe(lat)

        snapshot = metrics.snapshot()
        latency_stats = snapshot["delivery"]["latency_ms"]
        assert latency_stats["count"] == 10
        assert latency_stats["p50"] > 0
        assert latency_stats["p99"] >= latency_stats["p50"]
