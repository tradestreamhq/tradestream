"""Tests for orchestrator agent config."""

from services.orchestrator_agent import config


class TestConfigValues:
    def test_signal_generator_interval(self):
        assert config.SIGNAL_GENERATOR_INTERVAL_SECONDS == 60

    def test_strategy_proposer_interval(self):
        assert config.STRATEGY_PROPOSER_INTERVAL_SECONDS == 1800

    def test_circuit_breaker_threshold(self):
        assert config.CIRCUIT_BREAKER_FAILURE_THRESHOLD == 3

    def test_circuit_breaker_recovery(self):
        assert config.CIRCUIT_BREAKER_RECOVERY_SECONDS == 300

    def test_retry_settings(self):
        assert config.RETRY_MAX_ATTEMPTS == 3
        assert config.RETRY_BASE_DELAY_SECONDS == 1.0
        assert config.RETRY_MAX_DELAY_SECONDS == 30.0
        assert config.RETRY_BACKOFF_MULTIPLIER == 2.0

    def test_agent_names(self):
        assert config.AGENT_SIGNAL_GENERATOR == "signal_generator"
        assert config.AGENT_OPPORTUNITY_SCORER == "opportunity_scorer"
        assert config.AGENT_STRATEGY_PROPOSER == "strategy_proposer"
