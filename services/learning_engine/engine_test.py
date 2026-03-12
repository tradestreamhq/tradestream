"""Tests for the Learning Engine."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest

from services.learning_engine.engine import (
    BIAS_THRESHOLDS,
    HistoricalContext,
    LearningEngine,
    PerformanceReport,
)


# ── Fixtures ────────────────────────────────────────────────────────────


def _mock_engine():
    """Create an engine with a mocked connection."""
    conn = mock.Mock()
    return LearningEngine(connection=conn), conn


def _mock_cursor(conn, rows=None, columns=None):
    """Set up mock cursor to return specified rows."""
    cur = mock.Mock()
    if columns:
        cur.description = [(col,) for col in columns]
    else:
        cur.description = None
    if rows is not None:
        cur.fetchall.return_value = rows
    conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
    conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)
    return cur


# ── HistoricalContext Tests ─────────────────────────────────────────────


class TestHistoricalContext:
    def test_defaults(self):
        ctx = HistoricalContext()
        assert ctx.recent_decisions == []
        assert ctx.win_rate is None
        assert ctx.avg_hold_time is None
        assert ctx.best_conditions == []
        assert ctx.worst_conditions == []
        assert ctx.detected_biases == []
        assert ctx.pnl_by_confidence == {}

    def test_to_dict(self):
        ctx = HistoricalContext(
            win_rate=0.65, detected_biases=[{"type": "overconfidence"}]
        )
        d = ctx.to_dict()
        assert d["win_rate"] == 0.65
        assert len(d["detected_biases"]) == 1

    def test_to_dict_with_hold_time(self):
        ctx = HistoricalContext(avg_hold_time=3600.0)
        d = ctx.to_dict()
        assert d["avg_hold_time"] == "3600.0"

    def test_to_dict_none_hold_time(self):
        ctx = HistoricalContext(avg_hold_time=None)
        d = ctx.to_dict()
        assert d["avg_hold_time"] is None

    def test_to_dict_all_fields(self):
        ctx = HistoricalContext(
            recent_decisions=[{"id": "1"}],
            win_rate=0.75,
            avg_hold_time=7200.0,
            best_conditions=[{"action": "BUY"}],
            worst_conditions=[{"action": "SELL"}],
            detected_biases=[{"bias_type": "loss_aversion"}],
            pnl_by_confidence={"high": {"avg_pnl": 2.0, "count": 5}},
        )
        d = ctx.to_dict()
        assert d["recent_decisions"] == [{"id": "1"}]
        assert d["win_rate"] == 0.75
        assert d["avg_hold_time"] == "7200.0"
        assert len(d["best_conditions"]) == 1
        assert len(d["worst_conditions"]) == 1
        assert d["pnl_by_confidence"]["high"]["avg_pnl"] == 2.0


# ── PerformanceReport Tests ────────────────────────────────────────────


class TestPerformanceReport:
    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        report = PerformanceReport(
            period_start=now,
            period_end=now,
            total_decisions=100,
            total_outcomes=80,
            win_rate=0.55,
            avg_pnl_percent=1.25,
            total_pnl=1000.0,
            max_drawdown=-5.0,
            best_instrument="BTC-USD",
            worst_instrument="DOGE-USD",
            patterns=[],
            biases=[],
        )
        d = report.to_dict()
        assert d["total_decisions"] == 100
        assert d["win_rate"] == 0.55
        assert d["best_instrument"] == "BTC-USD"

    def test_to_dict_none_dates(self):
        report = PerformanceReport(
            period_start=None,
            period_end=None,
            total_decisions=0,
            total_outcomes=0,
            win_rate=None,
            avg_pnl_percent=None,
            total_pnl=None,
            max_drawdown=None,
            best_instrument=None,
            worst_instrument=None,
            patterns=[],
            biases=[],
        )
        d = report.to_dict()
        assert d["period_start"] is None
        assert d["period_end"] is None

    def test_to_dict_preserves_all_fields(self):
        now = datetime.now(timezone.utc)
        report = PerformanceReport(
            period_start=now,
            period_end=now,
            total_decisions=10,
            total_outcomes=8,
            win_rate=0.625,
            avg_pnl_percent=2.5,
            total_pnl=500.0,
            max_drawdown=-3.0,
            best_instrument="SOL-USD",
            worst_instrument="SHIB-USD",
            patterns=[{"type": "strong_strategy"}],
            biases=[{"type": "overconfidence"}],
        )
        d = report.to_dict()
        assert d["total_outcomes"] == 8
        assert d["avg_pnl_percent"] == 2.5
        assert d["total_pnl"] == 500.0
        assert d["max_drawdown"] == -3.0
        assert d["worst_instrument"] == "SHIB-USD"
        assert len(d["patterns"]) == 1
        assert len(d["biases"]) == 1


# ── Record Outcome Tests ───────────────────────────────────────────────


class TestRecordOutcome:
    def test_records_buy_outcome(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        outcome_id = engine.record_outcome(
            decision_id="dec-1",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=52000,
            exit_reason="target_hit",
        )

        assert outcome_id is not None
        cur.execute.assert_called_once()
        call_args = cur.execute.call_args
        params = call_args[0][1]
        # pnl_absolute = 52000 - 50000 = 2000
        assert params[7] == 2000.0
        # pnl_percent = (2000/50000) * 100 = 4.0
        assert params[8] == 4.0
        conn.commit.assert_called_once()

    def test_records_sell_outcome(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-2",
            instrument="ETH-USD",
            action="SELL",
            entry_price=3000,
            exit_price=2800,
        )

        call_args = cur.execute.call_args
        params = call_args[0][1]
        # pnl_absolute for SELL = entry - exit = 200
        assert params[7] == 200.0

    def test_sell_losing_trade(self):
        """SELL where price goes up = loss."""
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-sell-loss",
            instrument="ETH-USD",
            action="SELL",
            entry_price=3000,
            exit_price=3200,
        )

        params = cur.execute.call_args[0][1]
        # pnl_absolute for SELL = 3000 - 3200 = -200
        assert params[7] == -200.0
        # pnl_percent = (-200 / 3000) * 100 ≈ -6.667
        assert abs(params[8] - (-6.6667)) < 0.01

    def test_handles_zero_entry_price(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-3",
            instrument="BTC-USD",
            action="BUY",
            entry_price=0,
            exit_price=100,
        )

        call_args = cur.execute.call_args
        params = call_args[0][1]
        # pnl should be None since entry_price is 0
        assert params[7] is None
        assert params[8] is None

    def test_handles_none_entry_price(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-none",
            instrument="BTC-USD",
            action="BUY",
            entry_price=None,
            exit_price=100,
        )

        params = cur.execute.call_args[0][1]
        assert params[7] is None
        assert params[8] is None

    def test_handles_none_exit_price(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-none-exit",
            instrument="BTC-USD",
            action="BUY",
            entry_price=100,
            exit_price=None,
        )

        params = cur.execute.call_args[0][1]
        assert params[7] is None
        assert params[8] is None

    def test_records_market_context_as_json(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        context = {"volatility": "high", "trend": "bullish", "volume": 1000000}
        engine.record_outcome(
            decision_id="dec-ctx",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=51000,
            market_context=context,
        )

        params = cur.execute.call_args[0][1]
        # market_context is JSON-serialized at index 11
        import json

        assert json.loads(params[11]) == context

    def test_records_none_market_context(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-no-ctx",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=51000,
            market_context=None,
        )

        params = cur.execute.call_args[0][1]
        assert params[11] is None

    def test_records_lessons_learned(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-lessons",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=51000,
            lessons_learned="Should have waited for confirmation",
        )

        params = cur.execute.call_args[0][1]
        assert params[12] == "Should have waited for confirmation"

    def test_records_hold_duration(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        hold = timedelta(hours=4, minutes=30)
        engine.record_outcome(
            decision_id="dec-hold",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=51000,
            hold_duration=hold,
        )

        params = cur.execute.call_args[0][1]
        assert params[9] == hold

    def test_records_custom_exit_timestamp(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        ts = datetime(2026, 3, 10, 14, 30, 0, tzinfo=timezone.utc)
        engine.record_outcome(
            decision_id="dec-ts",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=51000,
            exit_timestamp=ts,
        )

        params = cur.execute.call_args[0][1]
        assert params[6] == ts

    def test_rollback_on_error(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)
        cur.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            engine.record_outcome(
                decision_id="dec-4",
                instrument="BTC-USD",
                action="BUY",
                entry_price=100,
                exit_price=110,
            )

        conn.rollback.assert_called_once()

    def test_returns_unique_ids(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn)

        id1 = engine.record_outcome(
            decision_id="dec-a",
            instrument="BTC-USD",
            action="BUY",
            entry_price=100,
            exit_price=110,
        )
        id2 = engine.record_outcome(
            decision_id="dec-b",
            instrument="BTC-USD",
            action="BUY",
            entry_price=100,
            exit_price=110,
        )
        assert id1 != id2

    def test_breakeven_trade(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine.record_outcome(
            decision_id="dec-even",
            instrument="BTC-USD",
            action="BUY",
            entry_price=50000,
            exit_price=50000,
        )

        params = cur.execute.call_args[0][1]
        assert params[7] == 0.0  # pnl_absolute
        assert params[8] == 0.0  # pnl_percent


# ── Win Rate Tests ──────────────────────────────────────────────────────


class TestCalculateWinRate:
    def test_returns_win_rate(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(10, 7)], columns=["total", "wins"])

        rate = engine.calculate_win_rate("BTC-USD")
        assert rate == 0.7

    def test_returns_none_when_no_data(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(0, 0)], columns=["total", "wins"])

        rate = engine.calculate_win_rate("BTC-USD")
        assert rate is None

    def test_all_instruments(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(20, 12)], columns=["total", "wins"])

        rate = engine.calculate_win_rate()
        assert rate == 0.6

    def test_no_rows_returned(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[], columns=["total", "wins"])

        rate = engine.calculate_win_rate("BTC-USD")
        assert rate is None

    def test_perfect_win_rate(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(5, 5)], columns=["total", "wins"])

        rate = engine.calculate_win_rate("BTC-USD")
        assert rate == 1.0

    def test_zero_win_rate(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(5, 0)], columns=["total", "wins"])

        rate = engine.calculate_win_rate("BTC-USD")
        assert rate == 0.0


# ── Average Hold Time Tests ─────────────────────────────────────────────


class TestAvgHoldTime:
    def test_returns_avg_seconds(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(7200.0,)], columns=["avg_seconds"])

        avg = engine.calculate_avg_hold_time("BTC-USD")
        assert avg == 7200.0

    def test_returns_none_when_no_data(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[(None,)], columns=["avg_seconds"])

        avg = engine.calculate_avg_hold_time()
        assert avg is None

    def test_with_specific_instrument(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn, rows=[(3600.0,)], columns=["avg_seconds"])

        avg = engine.calculate_avg_hold_time("ETH-USD")
        assert avg == 3600.0
        # Verify the instrument was passed in the query
        call_args = cur.execute.call_args
        assert "ETH-USD" in call_args[0][1]


# ── Bias Detection Tests ────────────────────────────────────────────────


class TestDetectOverconfidence:
    def test_detects_overconfidence(self):
        engine, conn = _mock_engine()
        # High-confidence decisions with < 50% win rate
        _mock_cursor(
            conn,
            rows=[(10, 3, 85.0)],
            columns=["total", "wins", "avg_score"],
        )

        bias = engine._detect_overconfidence("BTC-USD")
        assert bias is not None
        assert bias["bias_type"] == "overconfidence"
        assert bias["win_rate"] == 0.3
        assert bias["total_decisions"] == 10
        assert bias["avg_score"] == 85.0
        assert "mitigation" in bias

    def test_no_overconfidence_when_winning(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(10, 8, 85.0)],
            columns=["total", "wins", "avg_score"],
        )

        bias = engine._detect_overconfidence("BTC-USD")
        assert bias is None

    def test_no_overconfidence_below_min_decisions(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(2, 0, 90.0)],
            columns=["total", "wins", "avg_score"],
        )

        bias = engine._detect_overconfidence()
        assert bias is None

    def test_overconfidence_at_threshold_boundary(self):
        """Exactly 50% win rate should NOT trigger overconfidence (< 0.5 required)."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(10, 5, 80.0)],
            columns=["total", "wins", "avg_score"],
        )

        bias = engine._detect_overconfidence("BTC-USD")
        assert bias is None

    def test_overconfidence_exactly_at_min_decisions(self):
        """Exactly at min_decisions threshold should proceed."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(5, 1, 75.0)],
            columns=["total", "wins", "avg_score"],
        )

        bias = engine._detect_overconfidence("BTC-USD")
        assert bias is not None
        assert bias["win_rate"] == 0.2

    def test_no_rows_returned(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn, rows=[], columns=["total", "wins", "avg_score"])

        bias = engine._detect_overconfidence()
        assert bias is None


class TestDetectLossAversion:
    def test_detects_loss_aversion(self):
        engine, conn = _mock_engine()
        # Losses held 3x longer than wins
        _mock_cursor(
            conn,
            rows=[
                ("win", 3600.0, 5),
                ("loss", 10800.0, 5),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is not None
        assert bias["bias_type"] == "loss_aversion"
        assert bias["ratio"] == 3.0
        assert "mitigation" in bias
        assert bias["loss_hold_avg_seconds"] == 10800.0
        assert bias["win_hold_avg_seconds"] == 3600.0

    def test_no_loss_aversion_when_balanced(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("win", 3600.0, 5),
                ("loss", 3600.0, 5),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None

    def test_no_bias_with_insufficient_data(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[("win", 3600.0, 1)],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None

    def test_no_bias_below_min_outcomes(self):
        """Total outcomes below threshold should not trigger."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("win", 3600.0, 2),
                ("loss", 10800.0, 2),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None

    def test_loss_aversion_at_exact_multiplier(self):
        """Exactly at 2.0x multiplier should trigger."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("win", 3600.0, 5),
                ("loss", 7200.0, 5),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is not None
        assert bias["ratio"] == 2.0

    def test_no_bias_just_below_multiplier(self):
        """Just below 2.0x multiplier should NOT trigger."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("win", 3600.0, 5),
                ("loss", 7199.0, 5),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None

    def test_handles_zero_win_hold_time(self):
        """Zero win hold time should not cause division by zero."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("win", 0.0, 5),
                ("loss", 7200.0, 5),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None

    def test_missing_loss_outcome(self):
        """Only win outcomes should return None."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("win", 3600.0, 10),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None

    def test_missing_win_outcome(self):
        """Only loss outcomes should return None."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("loss", 3600.0, 10),
            ],
            columns=["outcome", "avg_hold_seconds", "count"],
        )

        bias = engine._detect_loss_aversion()
        assert bias is None


class TestDetectBiases:
    def test_combines_both_biases(self):
        engine = LearningEngine(connection=mock.Mock())
        engine._detect_overconfidence = mock.Mock(
            return_value={"bias_type": "overconfidence", "win_rate": 0.3}
        )
        engine._detect_loss_aversion = mock.Mock(
            return_value={"bias_type": "loss_aversion", "ratio": 3.0}
        )

        biases = engine.detect_biases("BTC-USD")
        assert len(biases) == 2
        assert biases[0]["bias_type"] == "overconfidence"
        assert biases[1]["bias_type"] == "loss_aversion"

    def test_returns_empty_when_no_biases(self):
        engine = LearningEngine(connection=mock.Mock())
        engine._detect_overconfidence = mock.Mock(return_value=None)
        engine._detect_loss_aversion = mock.Mock(return_value=None)

        biases = engine.detect_biases("BTC-USD")
        assert biases == []

    def test_returns_only_detected_biases(self):
        engine = LearningEngine(connection=mock.Mock())
        engine._detect_overconfidence = mock.Mock(return_value=None)
        engine._detect_loss_aversion = mock.Mock(
            return_value={"bias_type": "loss_aversion", "ratio": 2.5}
        )

        biases = engine.detect_biases()
        assert len(biases) == 1
        assert biases[0]["bias_type"] == "loss_aversion"


# ── Pattern Detection Tests ─────────────────────────────────────────────


class TestDetectStrategyPatterns:
    def test_detects_strong_and_weak_strategies(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("signal_emission", 10, 8, 2.5, 1.0),
                ("scoring", 10, 3, -1.5, 2.0),
            ],
            columns=["decision_type", "total", "wins", "avg_pnl", "pnl_stddev"],
        )

        patterns = engine._detect_strategy_patterns("BTC-USD")
        assert len(patterns) == 2
        assert patterns[0]["pattern_type"] == "strong_strategy"
        assert patterns[0]["win_rate"] == 0.8
        assert patterns[0]["avg_pnl_impact"] == 2.5
        assert patterns[0]["decision_type"] == "signal_emission"
        assert patterns[0]["frequency"] == 10
        assert patterns[1]["pattern_type"] == "weak_strategy"
        assert patterns[1]["win_rate"] == 0.3

    def test_no_patterns_below_min_frequency(self):
        """Query has HAVING clause so empty rows means below threshold."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[],
            columns=["decision_type", "total", "wins", "avg_pnl", "pnl_stddev"],
        )

        patterns = engine._detect_strategy_patterns("BTC-USD", min_frequency=5)
        assert len(patterns) == 0

    def test_zero_pnl_is_weak_strategy(self):
        """Zero avg_pnl should not be classified as strong_strategy."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[("scoring", 10, 5, 0.0, 1.0)],
            columns=["decision_type", "total", "wins", "avg_pnl", "pnl_stddev"],
        )

        patterns = engine._detect_strategy_patterns()
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "weak_strategy"


class TestDetectTimePatterns:
    def test_detects_favorable_time(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(14, 10, 3.5)],
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns("BTC-USD")
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "favorable_time"
        assert patterns[0]["hour"] == 14
        assert patterns[0]["avg_pnl_impact"] == 3.5

    def test_detects_unfavorable_time(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(3, 10, -2.5)],
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns("BTC-USD")
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "unfavorable_time"
        assert patterns[0]["hour"] == 3

    def test_ignores_insignificant_patterns(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(10, 5, 0.2)],  # avg_pnl < 1.0, too small
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns()
        assert len(patterns) == 0

    def test_multiple_time_patterns(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                (9, 10, 4.0),
                (14, 8, 2.5),
                (22, 12, -3.0),
                (2, 6, 0.5),  # This one is insignificant
            ],
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns("BTC-USD")
        assert len(patterns) == 3
        favorable = [p for p in patterns if p["pattern_type"] == "favorable_time"]
        unfavorable = [p for p in patterns if p["pattern_type"] == "unfavorable_time"]
        assert len(favorable) == 2
        assert len(unfavorable) == 1

    def test_boundary_avg_pnl_exactly_one(self):
        """avg_pnl of exactly 1.0 should NOT be flagged (> 1.0 required)."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(10, 5, 1.0)],
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns()
        assert len(patterns) == 0

    def test_negative_boundary(self):
        """avg_pnl of exactly -1.0 should NOT be flagged (abs > 1.0 required)."""
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(10, 5, -1.0)],
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns()
        assert len(patterns) == 0


class TestDetectPatterns:
    def test_orchestrates_strategy_and_time_patterns(self):
        engine = LearningEngine(connection=mock.Mock())
        engine._detect_strategy_patterns = mock.Mock(
            return_value=[
                {
                    "pattern_type": "strong_strategy",
                    "description": "Test",
                    "frequency": 10,
                    "avg_pnl_impact": 2.5,
                }
            ]
        )
        engine._detect_time_patterns = mock.Mock(
            return_value=[
                {
                    "pattern_type": "favorable_time",
                    "description": "Test time",
                    "frequency": 8,
                    "avg_pnl_impact": 1.5,
                }
            ]
        )
        engine._store_pattern = mock.Mock()

        patterns = engine.detect_patterns("BTC-USD", min_frequency=3)
        assert len(patterns) == 2
        assert engine._store_pattern.call_count == 2

    def test_stores_each_pattern(self):
        engine = LearningEngine(connection=mock.Mock())
        engine._detect_strategy_patterns = mock.Mock(
            return_value=[
                {"pattern_type": "p1", "description": "d1"},
                {"pattern_type": "p2", "description": "d2"},
            ]
        )
        engine._detect_time_patterns = mock.Mock(return_value=[])
        engine._store_pattern = mock.Mock()

        engine.detect_patterns("ETH-USD")
        assert engine._store_pattern.call_count == 2
        engine._store_pattern.assert_any_call(
            {"pattern_type": "p1", "description": "d1"}, "ETH-USD"
        )

    def test_returns_empty_when_no_patterns(self):
        engine = LearningEngine(connection=mock.Mock())
        engine._detect_strategy_patterns = mock.Mock(return_value=[])
        engine._detect_time_patterns = mock.Mock(return_value=[])
        engine._store_pattern = mock.Mock()

        patterns = engine.detect_patterns()
        assert patterns == []
        engine._store_pattern.assert_not_called()


# ── Best/Worst Conditions Tests ─────────────────────────────────────────


class TestConditions:
    def test_get_best_conditions(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ({"volatility": "low"}, 5.0, "BUY", "target_hit", "BTC-USD"),
            ],
            columns=[
                "market_context",
                "pnl_percent",
                "action",
                "exit_reason",
                "instrument",
            ],
        )

        best = engine.get_best_conditions("BTC-USD")
        assert len(best) == 1
        assert best[0]["pnl_percent"] == 5.0
        assert best[0]["market_context"] == {"volatility": "low"}
        assert best[0]["action"] == "BUY"
        assert best[0]["instrument"] == "BTC-USD"

    def test_get_worst_conditions(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ({"volatility": "high"}, -8.0, "BUY", "stop_loss", "BTC-USD"),
            ],
            columns=[
                "market_context",
                "pnl_percent",
                "action",
                "exit_reason",
                "instrument",
            ],
        )

        worst = engine.get_worst_conditions("BTC-USD")
        assert len(worst) == 1
        assert worst[0]["pnl_percent"] == -8.0

    def test_get_best_conditions_all_instruments(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ({"trend": "up"}, 10.0, "BUY", "target_hit", "BTC-USD"),
                ({"trend": "up"}, 7.0, "BUY", "target_hit", "ETH-USD"),
            ],
            columns=[
                "market_context",
                "pnl_percent",
                "action",
                "exit_reason",
                "instrument",
            ],
        )

        best = engine.get_best_conditions(limit=2)
        assert len(best) == 2

    def test_empty_conditions(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[],
            columns=[
                "market_context",
                "pnl_percent",
                "action",
                "exit_reason",
                "instrument",
            ],
        )

        best = engine.get_best_conditions("BTC-USD")
        assert best == []

        worst = engine.get_worst_conditions("BTC-USD")
        assert worst == []


# ── P&L by Confidence Tests ────────────────────────────────────────────


class TestPnlByConfidence:
    def test_returns_bucketed_pnl(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                ("high", 3.5, 10),
                ("medium", 1.2, 15),
                ("low", -0.5, 5),
            ],
            columns=["confidence_bucket", "avg_pnl", "count"],
        )

        result = engine.get_pnl_by_confidence("BTC-USD")
        assert result["high"]["avg_pnl"] == 3.5
        assert result["high"]["count"] == 10
        assert result["medium"]["avg_pnl"] == 1.2
        assert result["low"]["avg_pnl"] == -0.5

    def test_empty_data(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[],
            columns=["confidence_bucket", "avg_pnl", "count"],
        )

        result = engine.get_pnl_by_confidence("BTC-USD")
        assert result == {}

    def test_single_bucket(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[("high", 5.0, 3)],
            columns=["confidence_bucket", "avg_pnl", "count"],
        )

        result = engine.get_pnl_by_confidence()
        assert len(result) == 1
        assert result["high"]["avg_pnl"] == 5.0


# ── Report Generation Tests ────────────────────────────────────────────


class TestGenerateReport:
    def test_generates_report(self):
        engine, conn = _mock_engine()

        # We need to mock multiple _execute_query calls
        call_count = [0]

        def mock_execute_query(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # Summary query
                return [
                    {
                        "total_decisions": 50,
                        "total_outcomes": 40,
                        "wins": 25,
                        "avg_pnl": 1.5,
                        "total_pnl": 3000.0,
                        "max_loss": -5.0,
                    }
                ]
            elif call_count[0] == 2:
                # Instrument stats query
                return [
                    {"instrument": "BTC-USD", "avg_pnl": 2.5, "trades": 20},
                    {"instrument": "ETH-USD", "avg_pnl": 0.5, "trades": 20},
                ]
            else:
                # Bias/pattern detection queries return empty
                return []

        engine._execute_query = mock_execute_query
        engine._execute_write = mock.Mock()

        report = engine.generate_report()
        assert report.total_decisions == 50
        assert report.total_outcomes == 40
        assert report.win_rate == 0.625
        assert report.best_instrument == "BTC-USD"
        assert report.worst_instrument == "ETH-USD"
        assert report.max_drawdown == -5.0
        assert report.avg_pnl_percent == 1.5
        assert report.total_pnl == 3000.0

    def test_generates_report_with_date_filter(self):
        engine, conn = _mock_engine()

        call_count = [0]
        captured_params = []

        def mock_execute_query(query, params=None):
            call_count[0] += 1
            captured_params.append(params)
            if call_count[0] == 1:
                return [
                    {
                        "total_decisions": 10,
                        "total_outcomes": 8,
                        "wins": 5,
                        "avg_pnl": 0.8,
                        "total_pnl": 400.0,
                        "max_loss": -2.0,
                    }
                ]
            elif call_count[0] == 2:
                return [{"instrument": "BTC-USD", "avg_pnl": 0.8, "trades": 8}]
            else:
                return []

        engine._execute_query = mock_execute_query
        engine._execute_write = mock.Mock()

        start = datetime(2026, 3, 1, tzinfo=timezone.utc)
        end = datetime(2026, 3, 10, tzinfo=timezone.utc)
        report = engine.generate_report(period_start=start, period_end=end)

        assert report.period_start == start
        assert report.period_end == end
        assert report.total_decisions == 10
        # Verify date params were passed
        assert start in captured_params[0]
        assert end in captured_params[0]

    def test_generates_report_with_no_data(self):
        engine, conn = _mock_engine()

        call_count = [0]

        def mock_execute_query(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {
                        "total_decisions": 0,
                        "total_outcomes": 0,
                        "wins": 0,
                        "avg_pnl": None,
                        "total_pnl": None,
                        "max_loss": None,
                    }
                ]
            elif call_count[0] == 2:
                return []
            else:
                return []

        engine._execute_query = mock_execute_query
        engine._execute_write = mock.Mock()

        report = engine.generate_report()
        assert report.total_decisions == 0
        assert report.total_outcomes == 0
        assert report.win_rate is None
        assert report.avg_pnl_percent is None
        assert report.total_pnl is None
        assert report.max_drawdown is None
        assert report.best_instrument is None
        assert report.worst_instrument is None

    def test_report_includes_biases_and_patterns(self):
        engine, conn = _mock_engine()

        call_count = [0]

        def mock_execute_query(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {
                        "total_decisions": 20,
                        "total_outcomes": 15,
                        "wins": 10,
                        "avg_pnl": 1.0,
                        "total_pnl": 500.0,
                        "max_loss": -3.0,
                    }
                ]
            elif call_count[0] == 2:
                return [{"instrument": "BTC-USD", "avg_pnl": 1.0, "trades": 15}]
            else:
                return []

        engine._execute_query = mock_execute_query
        engine._execute_write = mock.Mock()
        engine.detect_biases = mock.Mock(return_value=[{"bias_type": "overconfidence"}])
        engine.detect_patterns = mock.Mock(
            return_value=[{"pattern_type": "favorable_time"}]
        )

        report = engine.generate_report()
        assert len(report.biases) == 1
        assert len(report.patterns) == 1

    def test_report_serializable_via_to_dict(self):
        engine, conn = _mock_engine()

        call_count = [0]

        def mock_execute_query(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {
                        "total_decisions": 5,
                        "total_outcomes": 4,
                        "wins": 3,
                        "avg_pnl": 2.0,
                        "total_pnl": 100.0,
                        "max_loss": -1.0,
                    }
                ]
            elif call_count[0] == 2:
                return [{"instrument": "BTC-USD", "avg_pnl": 2.0, "trades": 4}]
            else:
                return []

        engine._execute_query = mock_execute_query
        engine._execute_write = mock.Mock()

        report = engine.generate_report()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "total_decisions" in d
        assert "win_rate" in d


# ── Reflection Prompt Tests ─────────────────────────────────────────────


class TestBuildReflectionPrompt:
    def test_builds_prompt_with_data(self):
        engine = LearningEngine(connection=mock.Mock())
        engine.get_historical_context = mock.Mock(
            return_value=HistoricalContext(
                win_rate=0.65,
                recent_decisions=[
                    {
                        "decision_type": "signal_emission",
                        "pnl_percent": 2.5,
                        "score": 85,
                    },
                ],
                detected_biases=[
                    {"bias_type": "overconfidence", "description": "test bias"},
                ],
                pnl_by_confidence={"high": {"avg_pnl": 3.0, "count": 10}},
                best_conditions=[{"action": "BUY", "pnl_percent": 5.0}],
                worst_conditions=[{"action": "BUY", "pnl_percent": -3.0}],
            )
        )

        prompt = engine.build_reflection_prompt("BTC-USD")

        assert "BTC-USD" in prompt
        assert "65.0%" in prompt
        assert "overconfidence" in prompt
        assert "signal_emission" in prompt
        assert "self-reflection" in prompt.lower()
        assert "high" in prompt
        assert "3.00%" in prompt
        assert "BEST PERFORMING" in prompt
        assert "WORST PERFORMING" in prompt

    def test_builds_prompt_with_no_data(self):
        engine = LearningEngine(connection=mock.Mock())
        engine.get_historical_context = mock.Mock(return_value=HistoricalContext())

        prompt = engine.build_reflection_prompt("BTC-USD")

        assert "BTC-USD" in prompt
        assert "self-reflection" in prompt.lower()
        # Should not include sections for empty data
        assert "YOUR WIN RATE" not in prompt
        assert "P&L BY CONFIDENCE" not in prompt
        assert "RECENT DECISIONS" not in prompt
        assert "DETECTED BIASES" not in prompt

    def test_builds_prompt_with_partial_data(self):
        """Only win_rate and recent decisions, no biases or conditions."""
        engine = LearningEngine(connection=mock.Mock())
        engine.get_historical_context = mock.Mock(
            return_value=HistoricalContext(
                win_rate=0.45,
                recent_decisions=[
                    {
                        "decision_type": "scoring",
                        "pnl_percent": None,
                        "score": 70,
                    },
                ],
            )
        )

        prompt = engine.build_reflection_prompt("ETH-USD")

        assert "ETH-USD" in prompt
        assert "45.0%" in prompt
        assert "pending" in prompt  # pnl_percent is None
        assert "DETECTED BIASES" not in prompt

    def test_builds_prompt_with_multiple_decisions(self):
        """Should show up to 5 recent decisions."""
        engine = LearningEngine(connection=mock.Mock())
        decisions = [
            {"decision_type": f"type_{i}", "pnl_percent": i * 1.0, "score": 50 + i}
            for i in range(8)
        ]
        engine.get_historical_context = mock.Mock(
            return_value=HistoricalContext(recent_decisions=decisions)
        )

        prompt = engine.build_reflection_prompt("BTC-USD")

        assert "RECENT DECISIONS (8)" in prompt
        # Only first 5 should appear in detail
        assert "type_0" in prompt
        assert "type_4" in prompt
        assert "type_5" not in prompt

    def test_builds_prompt_calls_get_historical_context(self):
        engine = LearningEngine(connection=mock.Mock())
        engine.get_historical_context = mock.Mock(return_value=HistoricalContext())

        engine.build_reflection_prompt("SOL-USD")

        engine.get_historical_context.assert_called_once_with("SOL-USD")

    def test_builds_prompt_multiple_confidence_buckets(self):
        engine = LearningEngine(connection=mock.Mock())
        engine.get_historical_context = mock.Mock(
            return_value=HistoricalContext(
                pnl_by_confidence={
                    "high": {"avg_pnl": 3.0, "count": 10},
                    "medium": {"avg_pnl": 1.0, "count": 20},
                    "low": {"avg_pnl": -0.5, "count": 5},
                }
            )
        )

        prompt = engine.build_reflection_prompt("BTC-USD")

        assert "P&L BY CONFIDENCE LEVEL" in prompt
        assert "high" in prompt
        assert "medium" in prompt
        assert "low" in prompt


# ── Connection Management Tests ─────────────────────────────────────────


class TestConnectionManagement:
    def test_uses_provided_connection(self):
        conn = mock.Mock()
        engine = LearningEngine(connection=conn)
        returned_conn, should_close = engine._get_connection()
        assert returned_conn is conn
        assert should_close is False

    @mock.patch("psycopg2.connect")
    def test_creates_connection_from_url(self, mock_connect):
        mock_conn = mock.Mock()
        mock_connect.return_value = mock_conn
        engine = LearningEngine(db_url="postgresql://localhost/test")
        returned_conn, should_close = engine._get_connection()
        assert returned_conn is mock_conn
        assert should_close is True
        mock_connect.assert_called_once_with("postgresql://localhost/test")


# ── Store Pattern Tests ─────────────────────────────────────────────────


class TestStorePattern:
    def test_stores_pattern(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine._store_pattern(
            {
                "pattern_type": "strong_strategy",
                "description": "Test pattern",
                "frequency": 10,
                "avg_pnl_impact": 2.5,
                "mitigation": "None needed",
            },
            instrument="BTC-USD",
        )

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    def test_stores_pattern_without_instrument(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine._store_pattern(
            {
                "pattern_type": "favorable_time",
                "description": "Time pattern",
                "frequency": 5,
                "avg_pnl_impact": 1.5,
            },
            instrument=None,
        )

        params = cur.execute.call_args[0][1]
        assert params[2] is None  # instrument

    def test_stores_pattern_missing_optional_fields(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine._store_pattern(
            {
                "pattern_type": "weak_strategy",
                "description": "Weak pattern",
            },
        )

        params = cur.execute.call_args[0][1]
        assert params[4] == 0  # frequency defaults to 0
        assert params[5] is None  # avg_pnl_impact
        assert params[6] is None  # mitigation


# ── Get Stored Patterns Tests ──────────────────────────────────────────


class TestGetStoredPatterns:
    def test_retrieves_patterns_for_instrument(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                {
                    "id": "p1",
                    "pattern_type": "strong_strategy",
                    "instrument": "BTC-USD",
                    "description": "Good strategy",
                    "frequency": 10,
                    "avg_pnl_impact": 2.5,
                    "detected_at": datetime.now(timezone.utc),
                }
            ],
            columns=[
                "id",
                "pattern_type",
                "instrument",
                "description",
                "frequency",
                "avg_pnl_impact",
                "detected_at",
            ],
        )

        patterns = engine.get_stored_patterns("BTC-USD")
        assert len(patterns) == 1

    def test_retrieves_all_patterns(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                {
                    "id": "p1",
                    "pattern_type": "strong_strategy",
                    "instrument": "BTC-USD",
                },
                {
                    "id": "p2",
                    "pattern_type": "favorable_time",
                    "instrument": None,
                },
            ],
            columns=["id", "pattern_type", "instrument"],
        )

        patterns = engine.get_stored_patterns()
        assert len(patterns) == 2

    def test_respects_limit(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(
            conn,
            rows=[],
            columns=["id", "pattern_type", "instrument"],
        )

        engine.get_stored_patterns(limit=5)
        call_args = cur.execute.call_args
        assert 5 in call_args[0][1]


# ── Recent Decisions Tests ──────────────────────────────────────────────


class TestGetRecentDecisions:
    def test_returns_formatted_decisions(self):
        engine, conn = _mock_engine()
        now = datetime.now(timezone.utc)
        _mock_cursor(
            conn,
            rows=[
                (
                    uuid.uuid4(),
                    now,
                    "signal_generator",
                    "signal_emission",
                    '{"symbol": "BTC-USD"}',
                    '{"action": "BUY"}',
                    85,
                    "Strong buy",
                    True,
                    "claude-haiku",
                    2.5,
                    1250.0,
                    timedelta(hours=2),
                    "target_hit",
                    50000,
                    51250,
                ),
            ],
            columns=[
                "id",
                "created_at",
                "agent_name",
                "decision_type",
                "input_context",
                "output",
                "score",
                "reasoning",
                "success",
                "model_used",
                "pnl_percent",
                "pnl_absolute",
                "hold_duration",
                "exit_reason",
                "entry_price",
                "exit_price",
            ],
        )

        decisions = engine.get_recent_decisions("BTC-USD", limit=5)
        assert len(decisions) == 1
        assert decisions[0]["pnl_percent"] == 2.5
        assert decisions[0]["pnl_absolute"] == 1250.0
        assert decisions[0]["exit_reason"] == "target_hit"
        assert decisions[0]["success"] is True
        assert decisions[0]["agent_name"] == "signal_generator"
        assert decisions[0]["decision_type"] == "signal_emission"
        assert decisions[0]["score"] == 85.0
        assert decisions[0]["reasoning"] == "Strong buy"
        assert decisions[0]["hold_duration"] is not None
        assert decisions[0]["timestamp"] is not None

    def test_handles_none_fields(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[
                (
                    uuid.uuid4(),
                    None,  # created_at
                    "agent",
                    "scoring",
                    "{}",
                    "{}",
                    None,  # score
                    None,  # reasoning
                    False,
                    "model",
                    None,  # pnl_percent
                    None,  # pnl_absolute
                    None,  # hold_duration
                    None,  # exit_reason
                    None,
                    None,
                ),
            ],
            columns=[
                "id",
                "created_at",
                "agent_name",
                "decision_type",
                "input_context",
                "output",
                "score",
                "reasoning",
                "success",
                "model_used",
                "pnl_percent",
                "pnl_absolute",
                "hold_duration",
                "exit_reason",
                "entry_price",
                "exit_price",
            ],
        )

        decisions = engine.get_recent_decisions("BTC-USD")
        assert len(decisions) == 1
        assert decisions[0]["timestamp"] is None
        assert decisions[0]["score"] is None
        assert decisions[0]["pnl_percent"] is None
        assert decisions[0]["pnl_absolute"] is None
        assert decisions[0]["hold_duration"] is None
        assert decisions[0]["exit_reason"] is None

    def test_returns_empty_list(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[],
            columns=[
                "id",
                "created_at",
                "agent_name",
                "decision_type",
                "input_context",
                "output",
                "score",
                "reasoning",
                "success",
                "model_used",
                "pnl_percent",
                "pnl_absolute",
                "hold_duration",
                "exit_reason",
                "entry_price",
                "exit_price",
            ],
        )

        decisions = engine.get_recent_decisions("BTC-USD")
        assert decisions == []


# ── Historical Context Integration Tests ────────────────────────────────


class TestGetHistoricalContext:
    def test_aggregates_all_sub_queries(self):
        """Verify get_historical_context calls all the right methods."""
        engine = LearningEngine(connection=mock.Mock())
        engine.get_recent_decisions = mock.Mock(return_value=[{"id": "d1"}])
        engine.calculate_win_rate = mock.Mock(return_value=0.65)
        engine.calculate_avg_hold_time = mock.Mock(return_value=7200.0)
        engine.get_best_conditions = mock.Mock(
            return_value=[{"action": "BUY", "pnl_percent": 5.0}]
        )
        engine.get_worst_conditions = mock.Mock(
            return_value=[{"action": "SELL", "pnl_percent": -3.0}]
        )
        engine.detect_biases = mock.Mock(return_value=[{"bias_type": "overconfidence"}])
        engine.get_pnl_by_confidence = mock.Mock(
            return_value={"high": {"avg_pnl": 3.0, "count": 5}}
        )

        ctx = engine.get_historical_context("BTC-USD", limit=20)

        assert ctx.recent_decisions == [{"id": "d1"}]
        assert ctx.win_rate == 0.65
        assert ctx.avg_hold_time == 7200.0
        assert len(ctx.best_conditions) == 1
        assert len(ctx.worst_conditions) == 1
        assert len(ctx.detected_biases) == 1
        assert "high" in ctx.pnl_by_confidence

        engine.get_recent_decisions.assert_called_once_with("BTC-USD", limit=20)
        engine.calculate_win_rate.assert_called_once_with("BTC-USD")
        engine.calculate_avg_hold_time.assert_called_once_with("BTC-USD")
        engine.get_best_conditions.assert_called_once_with("BTC-USD")
        engine.get_worst_conditions.assert_called_once_with("BTC-USD")
        engine.detect_biases.assert_called_once_with("BTC-USD")
        engine.get_pnl_by_confidence.assert_called_once_with("BTC-USD")

    def test_handles_all_none_results(self):
        engine = LearningEngine(connection=mock.Mock())
        engine.get_recent_decisions = mock.Mock(return_value=[])
        engine.calculate_win_rate = mock.Mock(return_value=None)
        engine.calculate_avg_hold_time = mock.Mock(return_value=None)
        engine.get_best_conditions = mock.Mock(return_value=[])
        engine.get_worst_conditions = mock.Mock(return_value=[])
        engine.detect_biases = mock.Mock(return_value=[])
        engine.get_pnl_by_confidence = mock.Mock(return_value={})

        ctx = engine.get_historical_context("DOGE-USD")

        assert ctx.recent_decisions == []
        assert ctx.win_rate is None
        assert ctx.avg_hold_time is None
        assert ctx.best_conditions == []
        assert ctx.worst_conditions == []
        assert ctx.detected_biases == []
        assert ctx.pnl_by_confidence == {}


# ── Execute Query/Write Tests ──────────────────────────────────────────


class TestExecuteQuery:
    def test_returns_dicts_from_rows(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[("BTC-USD", 2.5), ("ETH-USD", 1.0)],
            columns=["instrument", "avg_pnl"],
        )

        results = engine._execute_query("SELECT instrument, avg_pnl FROM test")
        assert len(results) == 2
        assert results[0]["instrument"] == "BTC-USD"
        assert results[0]["avg_pnl"] == 2.5
        assert results[1]["instrument"] == "ETH-USD"

    def test_returns_empty_when_no_description(self):
        engine, conn = _mock_engine()
        _mock_cursor(conn)  # No columns = no description

        results = engine._execute_query("SELECT 1")
        assert results == []

    def test_passes_params(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn, rows=[], columns=["id"])

        engine._execute_query("SELECT id FROM t WHERE x = %s", ("val",))
        cur.execute.assert_called_once_with("SELECT id FROM t WHERE x = %s", ("val",))


class TestExecuteWrite:
    def test_commits_on_success(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)

        engine._execute_write("INSERT INTO t VALUES (%s)", ("val",))
        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    def test_rollback_on_failure(self):
        engine, conn = _mock_engine()
        cur = _mock_cursor(conn)
        cur.execute.side_effect = Exception("Write failed")

        with pytest.raises(Exception, match="Write failed"):
            engine._execute_write("INSERT INTO t VALUES (%s)", ("val",))

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()


# ── BIAS_THRESHOLDS Tests ──────────────────────────────────────────────


class TestBiasThresholds:
    def test_overconfidence_thresholds_defined(self):
        assert "overconfidence" in BIAS_THRESHOLDS
        assert BIAS_THRESHOLDS["overconfidence"]["min_confidence"] == 0.7
        assert BIAS_THRESHOLDS["overconfidence"]["max_win_rate"] == 0.5
        assert BIAS_THRESHOLDS["overconfidence"]["min_decisions"] == 5

    def test_loss_aversion_thresholds_defined(self):
        assert "loss_aversion" in BIAS_THRESHOLDS
        assert BIAS_THRESHOLDS["loss_aversion"]["loss_hold_multiplier"] == 2.0
        assert BIAS_THRESHOLDS["loss_aversion"]["min_outcomes"] == 5

    def test_recency_bias_thresholds_defined(self):
        assert "recency_bias" in BIAS_THRESHOLDS
        assert BIAS_THRESHOLDS["recency_bias"]["recent_weight_threshold"] == 0.7
        assert BIAS_THRESHOLDS["recency_bias"]["min_decisions"] == 10


# ── Integration-style Tests (Learning Feedback Loop) ───────────────────


class TestLearningFeedbackLoop:
    """Tests that verify the end-to-end feedback loop:
    record outcomes -> detect patterns/biases -> generate reflection prompt.
    """

    def test_full_loop_with_overconfidence(self):
        """Record outcomes showing overconfidence, verify it appears in reflection."""
        engine = LearningEngine(connection=mock.Mock())

        # Simulate the context that would result from overconfident trades
        engine.get_historical_context = mock.Mock(
            return_value=HistoricalContext(
                win_rate=0.3,
                recent_decisions=[
                    {"decision_type": "signal", "pnl_percent": -2.0, "score": 90},
                    {"decision_type": "signal", "pnl_percent": -1.5, "score": 85},
                    {"decision_type": "signal", "pnl_percent": 1.0, "score": 80},
                ],
                detected_biases=[
                    {
                        "bias_type": "overconfidence",
                        "description": "High-confidence decisions (score >= 70) have a win rate of 30.0%, suggesting overconfidence.",
                    }
                ],
                pnl_by_confidence={
                    "high": {"avg_pnl": -0.83, "count": 3},
                },
            )
        )

        prompt = engine.build_reflection_prompt("BTC-USD")

        assert "30.0%" in prompt
        assert "overconfidence" in prompt
        assert "high" in prompt

    def test_full_loop_with_loss_aversion(self):
        """Verify loss aversion detected from hold time disparity shows in prompt."""
        engine = LearningEngine(connection=mock.Mock())

        engine.get_historical_context = mock.Mock(
            return_value=HistoricalContext(
                win_rate=0.5,
                detected_biases=[
                    {
                        "bias_type": "loss_aversion",
                        "description": "Losing positions are held 3.0x longer than winning ones, suggesting loss aversion.",
                    }
                ],
            )
        )

        prompt = engine.build_reflection_prompt("ETH-USD")

        assert "loss_aversion" in prompt
        assert "3.0x longer" in prompt

    def test_full_loop_patterns_inform_decisions(self):
        """Verify detected patterns flow into the context correctly."""
        engine = LearningEngine(connection=mock.Mock())

        # Detect patterns
        engine._detect_strategy_patterns = mock.Mock(
            return_value=[
                {
                    "pattern_type": "strong_strategy",
                    "description": "Decision type 'signal_emission' has a 80.0% win rate",
                    "frequency": 10,
                    "avg_pnl_impact": 2.5,
                    "decision_type": "signal_emission",
                    "win_rate": 0.8,
                }
            ]
        )
        engine._detect_time_patterns = mock.Mock(return_value=[])
        engine._store_pattern = mock.Mock()

        patterns = engine.detect_patterns("BTC-USD")
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "strong_strategy"
        assert patterns[0]["decision_type"] == "signal_emission"

    def test_report_captures_full_state(self):
        """Generate report encapsulates decisions, outcomes, patterns, biases."""
        engine = LearningEngine(connection=mock.Mock())

        call_count = [0]

        def mock_execute_query(query, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {
                        "total_decisions": 30,
                        "total_outcomes": 25,
                        "wins": 15,
                        "avg_pnl": 1.2,
                        "total_pnl": 1500.0,
                        "max_loss": -4.0,
                    }
                ]
            elif call_count[0] == 2:
                return [
                    {"instrument": "BTC-USD", "avg_pnl": 2.0, "trades": 15},
                    {"instrument": "DOGE-USD", "avg_pnl": -1.0, "trades": 10},
                ]
            else:
                return []

        engine._execute_query = mock_execute_query
        engine._execute_write = mock.Mock()

        report = engine.generate_report()

        assert report.total_decisions == 30
        assert report.win_rate == 0.6
        assert report.best_instrument == "BTC-USD"
        assert report.worst_instrument == "DOGE-USD"

        # Verify it's serializable
        d = report.to_dict()
        assert d["total_pnl"] == 1500.0
        assert d["max_drawdown"] == -4.0
