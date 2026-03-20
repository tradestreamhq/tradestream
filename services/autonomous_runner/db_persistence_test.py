"""Tests for the database persistence layer."""

import pytest

from services.autonomous_runner.db_persistence import DecisionPersistence
from services.autonomous_runner.decision_models import AgentDecision


def test_unavailable_without_db_url():
    db = DecisionPersistence("")
    assert db.is_available is False


def test_persist_returns_false_when_unavailable():
    db = DecisionPersistence("")
    decision = AgentDecision(
        symbol="BTC-USD",
        action="BUY",
        confidence=0.85,
        reasoning="Test",
    )
    assert db.persist_decision(decision) is False


def test_get_recent_returns_empty_when_unavailable():
    db = DecisionPersistence("")
    assert db.get_recent_decisions() == []


def test_record_outcome_returns_false_when_unavailable():
    db = DecisionPersistence("")
    assert db.record_outcome("fake-id", 0.05, True) is False


def test_init_with_bad_url_is_graceful():
    db = DecisionPersistence("postgresql://nonexistent:5432/db")
    assert db.is_available is False


def test_close_without_pool():
    db = DecisionPersistence("")
    db.close()  # Should not raise
