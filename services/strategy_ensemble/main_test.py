"""Tests for the strategy ensemble service."""

from unittest import mock

import pytest

from absl import flags

from services.strategy_ensemble.main import (
    EnsembleStrategy,
    StrategyEnsemble,
    StrategyEnsembleBuilder,
)

FLAGS = flags.FLAGS


@pytest.fixture(autouse=True)
def _reset_flags():
    """Ensure flag defaults for each test."""
    saved = {
        "min_strategies_per_ensemble": FLAGS.min_strategies_per_ensemble,
        "max_strategies_per_ensemble": FLAGS.max_strategies_per_ensemble,
        "min_ensemble_score": FLAGS.min_ensemble_score,
        "diversification_weight": FLAGS.diversification_weight,
        "performance_weight": FLAGS.performance_weight,
        "require_diversification": FLAGS.require_diversification,
    }
    yield
    for k, v in saved.items():
        FLAGS[k].value = v


def _make_builder():
    builder = StrategyEnsembleBuilder.__new__(StrategyEnsembleBuilder)
    builder.db_config = {}
    builder.pool = None
    return builder


def _strategy(sid, symbol, stype, score):
    return {
        "strategy_id": sid,
        "symbol": symbol,
        "strategy_type": stype,
        "current_score": score,
    }


class TestCalculateEnsembleMetrics:
    def setup_method(self):
        self.builder = _make_builder()

    def test_empty_strategies(self):
        result = self.builder._calculate_ensemble_metrics([])
        assert result["total_score"] == 0.0
        assert result["weights"] == []

    def test_single_strategy(self):
        strategies = [_strategy("s1", "BTC", "RSI", 0.9)]
        result = self.builder._calculate_ensemble_metrics(strategies)
        assert result["performance_score"] == 0.9
        assert result["diversification_score"] == 1.0
        assert result["risk_score"] == 0.0
        assert len(result["weights"]) == 1
        assert result["weights"][0] == 1.0

    def test_two_different_types(self):
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.9),
            _strategy("s2", "BTC", "MACD", 0.8),
        ]
        result = self.builder._calculate_ensemble_metrics(strategies)
        assert result["performance_score"] == pytest.approx(0.85)
        assert result["diversification_score"] == 1.0  # 2 types / 2 strategies
        assert result["risk_score"] > 0.0  # non-zero variance
        assert len(result["weights"]) == 2
        assert result["weights"][0] == pytest.approx(0.5)

    def test_two_same_types(self):
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.9),
            _strategy("s2", "BTC", "RSI", 0.8),
        ]
        result = self.builder._calculate_ensemble_metrics(strategies)
        assert result["diversification_score"] == pytest.approx(0.5)

    def test_total_score_uses_weights(self):
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.9),
            _strategy("s2", "BTC", "MACD", 0.9),
        ]
        result = self.builder._calculate_ensemble_metrics(strategies)
        # total = 0.7 * perf + 0.3 * div - 0.1 * risk
        expected = 0.7 * 0.9 + 0.3 * 1.0 - 0.1 * 0.0
        assert result["total_score"] == pytest.approx(expected)

    def test_risk_score_increases_with_spread(self):
        tight = [
            _strategy("s1", "BTC", "RSI", 0.85),
            _strategy("s2", "BTC", "MACD", 0.85),
        ]
        spread = [
            _strategy("s1", "BTC", "RSI", 0.95),
            _strategy("s2", "BTC", "MACD", 0.75),
        ]
        r_tight = self.builder._calculate_ensemble_metrics(tight)
        r_spread = self.builder._calculate_ensemble_metrics(spread)
        assert r_spread["risk_score"] > r_tight["risk_score"]


class TestBuildEnsembles:
    def setup_method(self):
        self.builder = _make_builder()

    def test_empty_input(self):
        assert self.builder.build_ensembles([]) == []

    def test_groups_by_symbol(self):
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.95),
            _strategy("s2", "BTC", "MACD", 0.90),
            _strategy("s3", "ETH", "RSI", 0.92),
            _strategy("s4", "ETH", "MACD", 0.88),
        ]
        ensembles = self.builder.build_ensembles(strategies)
        symbols = {e.symbol for e in ensembles}
        assert "BTC" in symbols
        assert "ETH" in symbols

    def test_skips_non_diversified_when_required(self):
        FLAGS.require_diversification = True
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.95),
            _strategy("s2", "BTC", "RSI", 0.90),
        ]
        ensembles = self.builder.build_ensembles(strategies)
        assert len(ensembles) == 0

    def test_allows_non_diversified_when_not_required(self):
        FLAGS.require_diversification = False
        FLAGS.min_ensemble_score = 0.0
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.95),
            _strategy("s2", "BTC", "RSI", 0.90),
        ]
        ensembles = self.builder.build_ensembles(strategies)
        assert len(ensembles) > 0

    def test_skips_low_scoring_ensembles(self):
        FLAGS.min_ensemble_score = 0.99
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.7),
            _strategy("s2", "BTC", "MACD", 0.6),
        ]
        ensembles = self.builder.build_ensembles(strategies)
        assert len(ensembles) == 0

    def test_ensemble_strategies_have_correct_weights(self):
        FLAGS.min_ensemble_score = 0.0
        strategies = [
            _strategy("s1", "BTC", "RSI", 0.95),
            _strategy("s2", "BTC", "MACD", 0.90),
        ]
        ensembles = self.builder.build_ensembles(strategies)
        assert len(ensembles) > 0
        for es in ensembles[0].strategies:
            assert es.weight == pytest.approx(0.5)

    def test_not_enough_strategies(self):
        """Single strategy can't form an ensemble (min=2)."""
        strategies = [_strategy("s1", "BTC", "RSI", 0.95)]
        ensembles = self.builder.build_ensembles(strategies)
        assert len(ensembles) == 0
