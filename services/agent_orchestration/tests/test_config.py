"""Tests for agent orchestration config."""

from services.agent_orchestration import config


def test_defaults_are_sensible():
    assert config.DEFAULT_CYCLE_INTERVAL_SECONDS >= config.MIN_CYCLE_INTERVAL_SECONDS
    assert config.CANDIDATES_PER_CYCLE > 0
    assert config.MIN_SHARPE_RATIO > 0
    assert config.MIN_WIN_RATE > 0
    assert config.MAX_DRAWDOWN < 0
    assert 0 < config.INITIAL_ALLOCATION_WEIGHT < 1
    assert config.MAX_ALLOCATION_WEIGHT > config.INITIAL_ALLOCATION_WEIGHT


def test_retry_settings():
    assert config.RETRY_MAX_ATTEMPTS > 0
    assert config.RETRY_BASE_DELAY_SECONDS > 0
    assert config.RETRY_MAX_DELAY_SECONDS >= config.RETRY_BASE_DELAY_SECONDS


def test_phase_names():
    phases = {
        config.PHASE_DISCOVERY,
        config.PHASE_VALIDATION,
        config.PHASE_PROMOTION,
        config.PHASE_MONITORING,
    }
    assert len(phases) == 4  # All unique
