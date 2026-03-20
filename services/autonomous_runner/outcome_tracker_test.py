"""Tests for the outcome tracker."""

import pytest

from services.autonomous_runner.outcome_tracker import (
    OutcomeConfig,
    OutcomeResult,
    OutcomeTracker,
)


class FakeDB:
    """Fake database for testing."""

    def __init__(self, decisions=None, available=True):
        self._decisions = decisions or []
        self._available = available
        self.recorded_outcomes = []

    @property
    def is_available(self):
        return self._available

    def get_recent_decisions(self, limit=50, symbol=None):
        return self._decisions[:limit]

    def record_outcome(
        self, decision_id, actual_return, hit_target, exit_price=None, max_drawdown=None
    ):
        self.recorded_outcomes.append(
            {
                "decision_id": decision_id,
                "actual_return": actual_return,
                "hit_target": hit_target,
                "exit_price": exit_price,
                "max_drawdown": max_drawdown,
            }
        )
        return True


class TestOutcomeConfig:
    def test_defaults(self):
        config = OutcomeConfig()
        assert config.check_interval_seconds == 300
        assert config.lookback_hours == 24
        assert config.target_return_pct == 1.0

    def test_custom(self):
        config = OutcomeConfig(check_interval_seconds=60, target_return_pct=2.0)
        assert config.check_interval_seconds == 60
        assert config.target_return_pct == 2.0


class TestOutcomeResult:
    def test_creation(self):
        result = OutcomeResult(
            decision_id="test-123",
            symbol="BTC-USD",
            action="BUY",
            entry_confidence=0.85,
            actual_return=0.02,
            hit_target=True,
        )
        assert result.decision_id == "test-123"
        assert result.hit_target is True

    def test_entry_price_field(self):
        result = OutcomeResult(
            decision_id="test-456",
            symbol="ETH-USD",
            action="SELL",
            entry_confidence=0.70,
            entry_price=3500.0,
            exit_price=3400.0,
            actual_return=0.0286,
            hit_target=True,
        )
        assert result.entry_price == 3500.0
        assert result.exit_price == 3400.0


class TestOutcomeTracker:
    def test_no_db_returns_empty(self):
        db = FakeDB(available=False)
        tracker = OutcomeTracker(db=db)
        results = tracker.check_pending_outcomes()
        assert results == []

    def test_no_pending_decisions(self):
        db = FakeDB(decisions=[])
        tracker = OutcomeTracker(db=db)
        results = tracker.check_pending_outcomes()
        assert results == []

    def test_filters_hold_decisions(self):
        decisions = [
            {
                "decision_id": "d1",
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.5,
                "risk_approved": True,
                "opportunity_score": 50.0,
            }
        ]
        db = FakeDB(decisions=decisions)
        tracker = OutcomeTracker(db=db)
        results = tracker.check_pending_outcomes()
        assert results == []

    def test_filters_unapproved_decisions(self):
        decisions = [
            {
                "decision_id": "d1",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.8,
                "risk_approved": False,
                "opportunity_score": 60.0,
            }
        ]
        db = FakeDB(decisions=decisions)
        tracker = OutcomeTracker(db=db)
        results = tracker.check_pending_outcomes()
        assert results == []

    def test_evaluate_with_entry_price_fn(self):
        """Test outcome evaluation using entry_price_fn for stored entry prices."""
        decisions = [
            {
                "decision_id": "d1",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
                "risk_approved": True,
                "opportunity_score": 75.0,
            }
        ]
        db = FakeDB(decisions=decisions)

        def fake_mcp(tool, params):
            return {"price": 66000.0}

        entry_prices = {"d1": 65000.0}

        tracker = OutcomeTracker(
            db=db,
            mcp_call_fn=fake_mcp,
            entry_price_fn=lambda did: entry_prices.get(did),
        )
        results = tracker.check_pending_outcomes()
        assert len(results) == 1
        assert results[0].entry_price == 65000.0
        assert results[0].exit_price == 66000.0
        # 66000/65000 - 1 = ~0.015385 (1.5% return, > 1% target)
        assert results[0].actual_return > 0
        assert results[0].hit_target is True
        assert len(db.recorded_outcomes) == 1

    def test_evaluate_with_market_context_fallback(self):
        """Test fallback to market_context.current_price when entry_price_fn unavailable."""
        decisions = [
            {
                "decision_id": "d2",
                "symbol": "ETH-USD",
                "action": "SELL",
                "confidence": 0.75,
                "risk_approved": True,
                "market_context": {"current_price": 3500.0},
            }
        ]
        db = FakeDB(decisions=decisions)

        def fake_mcp(tool, params):
            return {"price": 3400.0}

        tracker = OutcomeTracker(db=db, mcp_call_fn=fake_mcp)
        results = tracker.check_pending_outcomes()
        assert len(results) == 1
        assert results[0].entry_price == 3500.0
        # SELL: -(3400-3500)/3500 = 0.0286 > 0.01 target
        assert results[0].actual_return > 0
        assert results[0].hit_target is True

    def test_evaluate_without_mcp_skips(self):
        decisions = [
            {
                "decision_id": "d1",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
                "risk_approved": True,
                "opportunity_score": 75.0,
            }
        ]
        db = FakeDB(decisions=decisions)
        tracker = OutcomeTracker(db=db, mcp_call_fn=None)
        results = tracker.check_pending_outcomes()
        assert len(results) == 0

    def test_stats(self):
        tracker = OutcomeTracker(db=FakeDB())
        stats = tracker.get_stats()
        assert stats["outcomes_recorded"] == 0
        assert stats["hit_rate"] == 0.0
        assert "pending_config" in stats

    def test_mcp_error_counted(self):
        decisions = [
            {
                "decision_id": "d1",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
                "risk_approved": True,
                "opportunity_score": 75.0,
            }
        ]
        db = FakeDB(decisions=decisions)

        def failing_mcp(tool, params):
            raise ConnectionError("MCP down")

        tracker = OutcomeTracker(db=db, mcp_call_fn=failing_mcp)
        results = tracker.check_pending_outcomes()
        assert len(results) == 0

    def test_buy_loss_does_not_hit_target(self):
        """Test that a losing BUY signal correctly reports as not hitting target."""
        decisions = [
            {
                "decision_id": "d3",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.80,
                "risk_approved": True,
                "market_context": {"current_price": 65000.0},
            }
        ]
        db = FakeDB(decisions=decisions)

        def fake_mcp(tool, params):
            return {"price": 64000.0}  # Price went down

        tracker = OutcomeTracker(db=db, mcp_call_fn=fake_mcp)
        results = tracker.check_pending_outcomes()
        assert len(results) == 1
        assert results[0].actual_return < 0
        assert results[0].hit_target is False
