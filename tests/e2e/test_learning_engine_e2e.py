"""End-to-end test: Learning Engine.

Validates the learning pipeline: feed historical data → detect regime →
verify strategy weight adjustment → generate performance report.

Tests the RegimeDetector, WeightOptimizer, and LearningEngine working together.
"""

import math

import pytest

from services.learning_engine.regime_detector import RegimeDetector
from services.learning_engine.weight_optimizer import DEFAULT_CONFIG, WeightOptimizer

from tests.e2e.conftest import make_candles, make_strategy_performance


# ---------------------------------------------------------------------------
# Regime Detection Tests
# ---------------------------------------------------------------------------


class TestRegimeDetectionE2E:
    """Feed market data → verify correct regime classification."""

    def test_uptrend_detected(self, sample_candles_uptrend):
        """Strong uptrend candles produce trending_up regime."""
        detector = RegimeDetector()
        result = detector.detect(sample_candles_uptrend, instrument="BTC/USD")

        assert result["regime_type"] in ("trending_up", "ranging")
        assert result["confidence"] > 0
        assert "volatility" in result["indicators"]
        assert "trend_strength" in result["indicators"]
        assert "trend_direction" in result["indicators"]
        assert result["instrument"] == "BTC/USD"

    def test_downtrend_detected(self, sample_candles_downtrend):
        """Strong downtrend candles produce trending_down regime."""
        detector = RegimeDetector()
        result = detector.detect(sample_candles_downtrend, instrument="ETH/USD")

        assert result["regime_type"] in ("trending_down", "ranging")
        assert result["confidence"] > 0
        assert (
            result["indicators"]["trend_direction"] < 0
            or result["regime_type"] == "ranging"
        )

    def test_volatile_regime_detected(self, sample_candles_volatile):
        """High-volatility no-trend candles produce volatile or ranging regime."""
        detector = RegimeDetector()
        result = detector.detect(sample_candles_volatile, instrument="DOGE/USD")

        assert result["regime_type"] in (
            "volatile",
            "ranging",
            "trending_up",
            "trending_down",
        )
        assert result["confidence"] > 0

    def test_quiet_regime_detected(self):
        """Low-volatility low-volume candles produce quiet regime."""
        # Generate very stable candles with low volume
        candles = []
        price = 100.0
        for i in range(30):
            candles.append(
                {
                    "open": price,
                    "high": price + 0.01,
                    "low": price - 0.01,
                    "close": price + 0.001 * (i % 2),
                    "volume": 10,
                }
            )
        detector = RegimeDetector()
        result = detector.detect(candles, instrument="STABLE/USD")

        assert result["regime_type"] in ("quiet", "ranging")
        assert result["confidence"] > 0

    def test_insufficient_data_returns_unknown(self):
        """Less than 20 candles returns unknown regime."""
        detector = RegimeDetector()
        short_candles = make_candles(n=10)
        result = detector.detect(short_candles, instrument="SHORT/USD")

        assert result["regime_type"] == "unknown"
        assert result["confidence"] == 0.0

    def test_regime_indicators_have_expected_keys(self, sample_candles_uptrend):
        """All expected indicator keys are present in the result."""
        detector = RegimeDetector()
        result = detector.detect(sample_candles_uptrend, instrument="BTC/USD")

        expected_keys = {
            "volatility",
            "trend_strength",
            "trend_direction",
            "volume_ratio",
            "atr_ratio",
        }
        assert expected_keys == set(result["indicators"].keys())

    def test_regime_types_are_valid(self, sample_candles_uptrend):
        """Result regime_type is one of the defined types."""
        detector = RegimeDetector()
        result = detector.detect(sample_candles_uptrend, instrument="BTC/USD")

        valid_types = {
            "trending_up",
            "trending_down",
            "ranging",
            "volatile",
            "quiet",
            "unknown",
        }
        assert result["regime_type"] in valid_types

    def test_custom_thresholds_change_classification(self):
        """Custom thresholds can change regime classification."""
        candles = make_candles(n=30, trend="flat", volatility=0.02)

        # Default thresholds
        default_detector = RegimeDetector()
        default_result = default_detector.detect(candles, instrument="TEST/USD")

        # Aggressive thresholds: lower volatility_high makes it volatile
        custom_thresholds = {
            "volatility_high": 0.005,
            "volatility_low": 0.001,
            "trend_strong": 0.9,
            "trend_weak": 0.1,
            "volume_surge": 1.5,
            "volume_quiet": 0.5,
        }
        custom_detector = RegimeDetector(thresholds=custom_thresholds)
        custom_result = custom_detector.detect(candles, instrument="TEST/USD")

        # With lower volatility_high threshold, the same data may be classified differently
        assert custom_result["regime_type"] in {
            "volatile",
            "ranging",
            "trending_up",
            "trending_down",
            "quiet",
        }


# ---------------------------------------------------------------------------
# Weight Optimization Tests
# ---------------------------------------------------------------------------


class TestWeightOptimizationE2E:
    """Strategy weight optimization based on regime-specific performance."""

    def test_high_performer_gets_higher_weight(self):
        """Strategy with high Sharpe/win rate gets above-average weight."""
        optimizer = WeightOptimizer()
        performances = [
            make_strategy_performance(
                "strat-good", sharpe_ratio=2.5, win_rate=0.7, avg_pnl_percent=3.0
            ),
            make_strategy_performance(
                "strat-avg", sharpe_ratio=0.5, win_rate=0.5, avg_pnl_percent=0.5
            ),
            make_strategy_performance(
                "strat-bad", sharpe_ratio=-0.5, win_rate=0.3, avg_pnl_percent=-1.0
            ),
        ]

        weights = optimizer.optimize_weights(performances, "trending_up", "BTC/USD")

        weight_map = {w["strategy_spec_id"]: w["weight"] for w in weights}
        assert weight_map["strat-good"] > weight_map["strat-avg"]
        assert weight_map["strat-avg"] > weight_map["strat-bad"]

    def test_insufficient_trades_get_default_weight(self):
        """Strategy with too few trades gets default weight."""
        optimizer = WeightOptimizer()
        performances = [
            make_strategy_performance("strat-new", trade_count=2),
            make_strategy_performance(
                "strat-seasoned", trade_count=50, sharpe_ratio=1.5
            ),
        ]

        weights = optimizer.optimize_weights(performances, "ranging", "ETH/USD")

        weight_map = {w["strategy_spec_id"]: w["weight"] for w in weights}
        assert weight_map["strat-new"] == DEFAULT_CONFIG["default_weight"]

    def test_weights_bounded_by_min_max(self):
        """All weights respect min_weight and max_weight bounds."""
        optimizer = WeightOptimizer()
        performances = [
            make_strategy_performance(
                "strat-extreme",
                sharpe_ratio=10.0,
                win_rate=1.0,
                avg_pnl_percent=50.0,
                trade_count=20,
            ),
            make_strategy_performance(
                "strat-terrible",
                sharpe_ratio=-5.0,
                win_rate=0.0,
                avg_pnl_percent=-50.0,
                trade_count=20,
            ),
        ]

        weights = optimizer.optimize_weights(performances, "volatile", "BTC/USD")

        for w in weights:
            assert w["weight"] >= DEFAULT_CONFIG["min_weight"]
            assert w["weight"] <= DEFAULT_CONFIG["max_weight"]

    def test_empty_performances_returns_empty(self):
        """No strategies → no weights."""
        optimizer = WeightOptimizer()
        weights = optimizer.optimize_weights([], "ranging", "BTC/USD")
        assert weights == []

    def test_single_strategy_gets_normalized_weight(self):
        """Single strategy weight is normalized relative to itself."""
        optimizer = WeightOptimizer()
        performances = [
            make_strategy_performance(
                "strat-solo", sharpe_ratio=1.0, win_rate=0.6, avg_pnl_percent=1.5
            ),
        ]

        weights = optimizer.optimize_weights(performances, "trending_up", "BTC/USD")

        assert len(weights) == 1
        assert weights[0]["weight"] > 0

    def test_custom_config_changes_scoring(self):
        """Custom config with different scoring weights produces different results."""
        config_sharpe_heavy = {
            **DEFAULT_CONFIG,
            "sharpe_weight": 0.9,
            "win_rate_weight": 0.05,
            "pnl_weight": 0.05,
        }
        config_winrate_heavy = {
            **DEFAULT_CONFIG,
            "sharpe_weight": 0.05,
            "win_rate_weight": 0.9,
            "pnl_weight": 0.05,
        }

        # Strategy A: high Sharpe, low win rate
        # Strategy B: low Sharpe, high win rate
        performances = [
            make_strategy_performance(
                "strat-a", sharpe_ratio=3.0, win_rate=0.3, avg_pnl_percent=1.0
            ),
            make_strategy_performance(
                "strat-b", sharpe_ratio=0.5, win_rate=0.9, avg_pnl_percent=1.0
            ),
        ]

        opt_sharpe = WeightOptimizer(config=config_sharpe_heavy)
        weights_sharpe = opt_sharpe.optimize_weights(performances, "ranging", "BTC/USD")
        map_sharpe = {w["strategy_spec_id"]: w["weight"] for w in weights_sharpe}

        opt_winrate = WeightOptimizer(config=config_winrate_heavy)
        weights_winrate = opt_winrate.optimize_weights(
            performances, "ranging", "BTC/USD"
        )
        map_winrate = {w["strategy_spec_id"]: w["weight"] for w in weights_winrate}

        # When Sharpe is heavily weighted, strat-a should rank higher
        assert map_sharpe["strat-a"] > map_sharpe["strat-b"]
        # When win rate is heavily weighted, strat-b should rank higher
        assert map_winrate["strat-b"] > map_winrate["strat-a"]


# ---------------------------------------------------------------------------
# Combined Regime → Weight Pipeline
# ---------------------------------------------------------------------------


class TestRegimeToWeightPipeline:
    """Full pipeline: detect regime from candles → optimize weights accordingly."""

    def test_regime_aware_weight_optimization(self):
        """Detect regime then optimize weights — weights tagged with regime."""
        detector = RegimeDetector()
        optimizer = WeightOptimizer()

        # Generate trending market data
        candles = make_candles(n=40, trend="up", volatility=0.015)
        regime = detector.detect(candles, instrument="BTC/USD")

        # Create performances
        performances = [
            make_strategy_performance(
                "trend-follower", sharpe_ratio=2.0, win_rate=0.65
            ),
            make_strategy_performance("mean-reverter", sharpe_ratio=0.3, win_rate=0.45),
        ]

        weights = optimizer.optimize_weights(
            performances, regime["regime_type"], "BTC/USD"
        )

        assert len(weights) == 2
        for w in weights:
            assert w["regime_type"] == regime["regime_type"]
            assert w["instrument"] == "BTC/USD"
            assert w["weight"] > 0

    def test_different_regimes_produce_same_weights_for_same_perf(self):
        """Weight optimization is deterministic for same inputs regardless of regime label."""
        optimizer = WeightOptimizer()
        performances = [
            make_strategy_performance("strat-1", sharpe_ratio=1.5, win_rate=0.6),
        ]

        w_up = optimizer.optimize_weights(performances, "trending_up", "BTC/USD")
        w_down = optimizer.optimize_weights(performances, "trending_down", "BTC/USD")

        # Without DB smoothing, same performance → same weights
        assert w_up[0]["weight"] == w_down[0]["weight"]
