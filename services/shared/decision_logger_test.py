"""Tests for the DecisionLogger shared library."""

import json
from unittest import mock

import pytest

from services.shared.decision_logger import DecisionLogger, _TrackingContext


def _make_mock_connection():
    """Create a mock psycopg2 connection with cursor context manager."""
    conn = mock.Mock()
    cursor = mock.Mock()
    conn.cursor.return_value.__enter__ = mock.Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)
    return conn, cursor


class TestDecisionLogger:
    """Tests for DecisionLogger.log_decision."""

    def test_log_decision_inserts_row(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        decision_id = logger.log_decision(
            agent_name="signal_generator",
            decision_type="signal_emission",
            input_context={"symbol": "BTC-USD"},
            output={"action": "BUY"},
            model_used="claude-3-5-haiku",
            tokens_used=1500,
            success=True,
        )

        assert decision_id is not None
        cursor.execute.assert_called_once()
        conn.commit.assert_called_once()

        # Verify the SQL contains INSERT INTO agent_decisions
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO agent_decisions" in sql

        # Verify params
        params = cursor.execute.call_args[0][1]
        assert params[0] == decision_id  # id
        assert params[10] == "signal_generator"  # agent_name
        assert params[11] == "signal_emission"  # decision_type
        assert json.loads(params[12]) == {"symbol": "BTC-USD"}  # input_context
        assert json.loads(params[13]) == {"action": "BUY"}  # output
        assert params[14] is True  # success

    def test_log_decision_with_none_optional_fields(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        decision_id = logger.log_decision(
            agent_name="orchestrator",
            decision_type="scheduling",
        )

        assert decision_id is not None
        params = cursor.execute.call_args[0][1]
        assert params[1] is None  # signal_id
        assert params[12] is None  # input_context (None, not "null")
        assert params[13] is None  # output

    def test_log_decision_rollback_on_error(self):
        conn, cursor = _make_mock_connection()
        cursor.execute.side_effect = Exception("DB error")
        logger = DecisionLogger(connection=conn)

        with pytest.raises(Exception, match="DB error"):
            logger.log_decision(
                agent_name="signal_generator",
                decision_type="signal_emission",
            )

        conn.rollback.assert_called_once()

    def test_log_decision_closes_connection_when_created(self):
        mock_conn = mock.Mock()
        mock_cursor = mock.Mock()
        mock_conn.cursor.return_value.__enter__ = mock.Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        with mock.patch("psycopg2.connect", return_value=mock_conn):
            logger = DecisionLogger(db_url="postgresql://localhost/test")
            logger.log_decision(
                agent_name="signal_generator",
                decision_type="signal_emission",
            )

        mock_conn.close.assert_called_once()

    def test_log_decision_does_not_close_shared_connection(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        logger.log_decision(
            agent_name="signal_generator",
            decision_type="signal_emission",
        )

        conn.close.assert_not_called()


class TestConvenienceMethods:
    """Tests for the agent-specific convenience methods."""

    def test_log_signal_decision(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        logger.log_signal_decision(
            signal_id="sig-123",
            input_context={"symbol": "BTC-USD"},
            output={"action": "BUY"},
        )

        params = cursor.execute.call_args[0][1]
        assert params[10] == "signal_generator"
        assert params[11] == "signal_emission"

    def test_log_scoring_decision(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        logger.log_scoring_decision(
            score=0.85,
            tier="high",
        )

        params = cursor.execute.call_args[0][1]
        assert params[10] == "opportunity_scorer"
        assert params[11] == "scoring"

    def test_log_proposal_decision(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        logger.log_proposal_decision(
            reasoning="Market gap identified",
        )

        params = cursor.execute.call_args[0][1]
        assert params[10] == "strategy_proposer"
        assert params[11] == "strategy_proposal"

    def test_log_orchestration_decision(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        logger.log_orchestration_decision(
            decision_type="circuit_break",
            reasoning="Too many failures",
        )

        params = cursor.execute.call_args[0][1]
        assert params[10] == "orchestrator"
        assert params[11] == "circuit_break"


class TestTrackContextManager:
    """Tests for the track() context manager."""

    def test_track_logs_on_success(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        with logger.track("signal_generator", "signal_emission") as ctx:
            ctx.input_context = {"symbol": "ETH-USD"}
            ctx.output = {"action": "SELL"}
            ctx.model_used = "claude-3-5-haiku"
            ctx.tokens_used = 800

        cursor.execute.assert_called_once()
        params = cursor.execute.call_args[0][1]
        assert params[10] == "signal_generator"
        assert params[14] is True  # success
        assert params[15] is None  # error_message
        assert params[7] is not None  # latency_ms (should be set)

    def test_track_logs_on_failure(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)

        with pytest.raises(ValueError, match="something broke"):
            with logger.track("signal_generator", "signal_emission") as ctx:
                ctx.input_context = {"symbol": "ETH-USD"}
                raise ValueError("something broke")

        cursor.execute.assert_called_once()
        params = cursor.execute.call_args[0][1]
        assert params[14] is False  # success
        assert params[15] == "something broke"  # error_message

    def test_track_passes_parent_decision_id(self):
        conn, cursor = _make_mock_connection()
        logger = DecisionLogger(connection=conn)
        parent_id = "parent-uuid-123"

        with logger.track("opportunity_scorer", "scoring", parent_id) as ctx:
            ctx.output = {"score": 0.9}

        params = cursor.execute.call_args[0][1]
        assert params[16] == parent_id  # parent_decision_id


class TestTrackingContext:
    """Tests for the _TrackingContext data holder."""

    def test_defaults(self):
        ctx = _TrackingContext("agent", "type")
        assert ctx.agent_name == "agent"
        assert ctx.decision_type == "type"
        assert ctx.signal_id is None
        assert ctx.input_context is None
        assert ctx.output is None
        assert ctx._success is True
        assert ctx._error_message is None

    def test_settable_fields(self):
        ctx = _TrackingContext("agent", "type")
        ctx.signal_id = "sig-1"
        ctx.input_context = {"key": "value"}
        ctx.output = {"result": True}
        ctx.score = 0.9
        ctx.tier = "high"
        ctx.reasoning = "because"
        ctx.tool_calls = [{"name": "tool1"}]
        ctx.model_used = "gpt-4"
        ctx.tokens_used = 500

        assert ctx.signal_id == "sig-1"
        assert ctx.tokens_used == 500
