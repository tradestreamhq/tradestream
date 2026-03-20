"""Tests for decision query service.

Tests the analytics query functions defined in the agent decisions schema spec.
Uses mock database connections since we don't require a live Postgres instance.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.autonomous_runner.decision_queries import (
    DecisionQueryService,
    _rows_to_dicts,
)


class TestDecisionQueryServiceUnavailable:
    """Tests for when database is not available."""

    def test_is_available_false_without_pool(self):
        svc = DecisionQueryService()
        assert svc.is_available is False

    def test_dashboard_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.get_dashboard_decisions() == []

    def test_symbol_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.get_decisions_by_symbol("BTC-USD") == []

    def test_high_opportunity_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.get_high_opportunity_decisions() == []

    def test_tool_performance_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.analyze_tool_performance() == []

    def test_model_usage_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.track_model_usage() == []

    def test_accuracy_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.calculate_accuracy() == []

    def test_find_by_tool_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.find_decisions_by_tool("get_top_strategies") == []

    def test_find_by_strategy_returns_empty_when_unavailable(self):
        svc = DecisionQueryService()
        assert svc.find_decisions_by_strategy("RSI_REVERSAL") == []


class TestDecisionQueryServiceWithMockDB:
    """Tests with a mock database pool."""

    def _make_service(self):
        pool = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        return DecisionQueryService(db_pool=pool), cursor

    def test_is_available_true_with_pool(self):
        svc, _ = self._make_service()
        assert svc.is_available is True

    def test_dashboard_decisions_query(self):
        svc, cursor = self._make_service()
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("id-1", "BTC-USD", "BUY", 0.85, 78.5, "GOOD", "Strong signal", {}, now),
        ]
        results = svc.get_dashboard_decisions(hours=24, min_opportunity_score=50)
        assert len(results) == 1
        assert results[0]["symbol"] == "BTC-USD"
        assert results[0]["action"] == "BUY"
        assert results[0]["opportunity_score"] == 78.5
        cursor.execute.assert_called_once()

    def test_decisions_by_symbol(self):
        svc, cursor = self._make_service()
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("id-1", "ETH-USD", "SELL", 0.72, 65.0, "GOOD",
             "Bearish", {}, {}, {}, True, 120, now),
        ]
        results = svc.get_decisions_by_symbol("ETH-USD", days=7, limit=10)
        assert len(results) == 1
        assert results[0]["symbol"] == "ETH-USD"
        assert results[0]["risk_approved"] is True

    def test_high_opportunity_decisions(self):
        svc, cursor = self._make_service()
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("id-1", "BTC-USD", "BUY", 0.92, 88.5, "HOT", "Very strong", now),
            ("id-2", "SOL-USD", "BUY", 0.88, 82.0, "HOT", "Strong too", now),
        ]
        results = svc.get_high_opportunity_decisions(min_score=80, hours=1)
        assert len(results) == 2
        assert results[0]["opportunity_tier"] == "HOT"

    def test_tool_performance_analysis(self):
        svc, cursor = self._make_service()
        cursor.fetchall.return_value = [
            ("get_top_strategies", 45.0, 100),
            ("get_market_summary", 32.0, 100),
            ("emit_signal", 28.0, 50),
        ]
        results = svc.analyze_tool_performance(hours=24)
        assert len(results) == 3
        assert results[0]["tool_name"] == "get_top_strategies"
        assert results[0]["avg_latency_ms"] == 45.0

    def test_model_usage_tracking(self):
        svc, cursor = self._make_service()
        cursor.fetchall.return_value = [
            ("google/gemini-3.0-flash", "autonomous_runner", 500, 85.0, 100000, 50000),
        ]
        results = svc.track_model_usage(hours=24)
        assert len(results) == 1
        assert results[0]["model_used"] == "google/gemini-3.0-flash"
        assert results[0]["decisions"] == 500

    def test_accuracy_calculation(self):
        svc, cursor = self._make_service()
        cursor.fetchall.return_value = [
            ("BTC-USD", "BUY", 100, 72, 0.72, 0.035, -0.012),
            ("ETH-USD", "BUY", 80, 52, 0.65, 0.028, -0.015),
        ]
        results = svc.calculate_accuracy(days=30)
        assert len(results) == 2
        assert results[0]["accuracy"] == 0.72
        assert results[0]["correct_decisions"] == 72

    def test_find_by_tool(self):
        svc, cursor = self._make_service()
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("id-1", "BTC-USD", "BUY", 0.85, 78.5, 120, now),
        ]
        results = svc.find_decisions_by_tool("get_top_strategies", limit=10)
        assert len(results) == 1
        # Verify the JSONB containment query was used
        call_args = cursor.execute.call_args
        assert "@>" in call_args[0][0]

    def test_find_by_strategy(self):
        svc, cursor = self._make_service()
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("id-1", "BTC-USD", "BUY", 0.85, 78.5, {"top_strategy": "RSI_REVERSAL"}, now),
        ]
        results = svc.find_decisions_by_strategy("RSI_REVERSAL")
        assert len(results) == 1
        assert "@>" in cursor.execute.call_args[0][0]

    def test_db_error_returns_empty_list(self):
        svc, cursor = self._make_service()
        cursor.execute.side_effect = Exception("Connection lost")
        assert svc.get_dashboard_decisions() == []
        assert svc.get_decisions_by_symbol("BTC") == []
        assert svc.get_high_opportunity_decisions() == []
        assert svc.analyze_tool_performance() == []
        assert svc.track_model_usage() == []
        assert svc.calculate_accuracy() == []
        assert svc.find_decisions_by_tool("foo") == []
        assert svc.find_decisions_by_strategy("foo") == []


class TestRowsToDicts:
    """Tests for the _rows_to_dicts helper."""

    def test_basic_conversion(self):
        rows = [("a", 1, 0.123456)]
        cols = ["name", "count", "score"]
        result = _rows_to_dicts(rows, cols)
        assert result == [{"name": "a", "count": 1, "score": 0.1235}]

    def test_datetime_serialization(self):
        dt = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        rows = [(dt,)]
        cols = ["ts"]
        result = _rows_to_dicts(rows, cols)
        assert result[0]["ts"] == "2026-03-20T12:00:00+00:00"

    def test_empty_rows(self):
        assert _rows_to_dicts([], ["a", "b"]) == []
