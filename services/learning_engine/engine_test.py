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
        assert ctx.detected_biases == []

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
        assert patterns[1]["pattern_type"] == "weak_strategy"


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

    def test_ignores_insignificant_patterns(self):
        engine, conn = _mock_engine()
        _mock_cursor(
            conn,
            rows=[(10, 5, 0.2)],  # avg_pnl < 1.0, too small
            columns=["hour", "total", "avg_pnl"],
        )

        patterns = engine._detect_time_patterns()
        assert len(patterns) == 0


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
        assert result["low"]["avg_pnl"] == -0.5


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

    def test_builds_prompt_with_no_data(self):
        engine = LearningEngine(connection=mock.Mock())
        engine.get_historical_context = mock.Mock(return_value=HistoricalContext())

        prompt = engine.build_reflection_prompt("BTC-USD")

        assert "BTC-USD" in prompt
        assert "self-reflection" in prompt.lower()


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
        assert decisions[0]["exit_reason"] == "target_hit"
        assert decisions[0]["success"] is True
