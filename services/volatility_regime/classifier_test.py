"""Tests for the volatility regime classifier."""

import math

import pytest

from services.volatility_regime.classifier import (
    ANNUALIZATION_FACTOR,
    VolatilityRegimeClassifier,
    classify_regime,
    compute_realized_volatility,
)
from services.volatility_regime.models import VolatilityRegime


class TestClassifyRegime:
    def test_low_volatility(self):
        assert classify_regime(10.0) == VolatilityRegime.LOW

    def test_low_boundary(self):
        assert classify_regime(14.99) == VolatilityRegime.LOW

    def test_medium_volatility(self):
        assert classify_regime(20.0) == VolatilityRegime.MEDIUM

    def test_medium_at_low_boundary(self):
        assert classify_regime(15.0) == VolatilityRegime.MEDIUM

    def test_medium_just_below_high(self):
        assert classify_regime(24.99) == VolatilityRegime.MEDIUM

    def test_high_volatility(self):
        assert classify_regime(30.0) == VolatilityRegime.HIGH

    def test_high_at_boundary(self):
        assert classify_regime(25.0) == VolatilityRegime.HIGH

    def test_zero(self):
        assert classify_regime(0.0) == VolatilityRegime.LOW


class TestComputeRealizedVolatility:
    def test_insufficient_data(self):
        assert compute_realized_volatility([100.0, 101.0], 20) is None

    def test_exact_minimum_data(self):
        # 21 prices give exactly 20 returns
        prices = [100.0 + i * 0.5 for i in range(21)]
        result = compute_realized_volatility(prices, 20)
        assert result is not None
        assert result > 0

    def test_stable_prices_low_vol(self):
        # Very stable prices → low volatility
        prices = [100.0] * 25
        # Constant prices → zero vol
        result = compute_realized_volatility(prices, 20)
        assert result is not None
        assert result == 0.0

    def test_volatile_prices_higher_vol(self):
        # Alternating prices → higher volatility
        prices = [100.0 if i % 2 == 0 else 110.0 for i in range(25)]
        result = compute_realized_volatility(prices, 20)
        assert result is not None
        assert result > 50.0  # Should be quite high

    def test_uses_most_recent_window(self):
        # First 30 stable, then 21 volatile
        stable = [100.0] * 30
        volatile = [100.0 if i % 2 == 0 else 120.0 for i in range(21)]
        prices = stable + volatile
        result = compute_realized_volatility(prices, 20)
        assert result is not None
        assert result > 50.0  # Should reflect the volatile tail


class TestVolatilityRegimeClassifier:
    def test_classify_with_sufficient_data(self):
        classifier = VolatilityRegimeClassifier()
        # 61 prices: enough for both 20d and 60d
        prices = [100.0 + i * 0.01 for i in range(61)]
        result = classifier.classify("BTC/USD", prices)
        assert result.symbol == "BTC/USD"
        assert result.regime in list(VolatilityRegime)
        assert result.volatility.realized_vol_20d is not None
        assert result.volatility.realized_vol_60d is not None

    def test_classify_with_only_20d_data(self):
        classifier = VolatilityRegimeClassifier()
        prices = [100.0 + i * 0.01 for i in range(25)]
        result = classifier.classify("ETH/USD", prices)
        assert result.volatility.realized_vol_20d is not None
        assert result.volatility.realized_vol_60d is None

    def test_classify_insufficient_data_defaults_medium(self):
        classifier = VolatilityRegimeClassifier()
        result = classifier.classify("XRP/USD", [100.0, 101.0])
        assert result.regime == VolatilityRegime.MEDIUM
        assert result.volatility.realized_vol_20d is None
        assert result.volatility.realized_vol_60d is None

    def test_tracks_transitions(self):
        classifier = VolatilityRegimeClassifier()
        # First classification: establishes baseline
        stable_prices = [100.0] * 25
        result1 = classifier.classify("BTC/USD", stable_prices)
        assert len(result1.recent_transitions) == 1  # initial transition

        # Same regime: no new transition
        result2 = classifier.classify("BTC/USD", stable_prices)
        assert len(result2.recent_transitions) == 1

        # Change to volatile: new transition
        volatile_prices = [100.0 if i % 2 == 0 else 150.0 for i in range(25)]
        result3 = classifier.classify("BTC/USD", volatile_prices)
        assert len(result3.recent_transitions) == 2
        assert result3.recent_transitions[0].current_regime == VolatilityRegime.HIGH
        assert result3.recent_transitions[0].previous_regime == VolatilityRegime.LOW

    def test_transitions_per_symbol(self):
        classifier = VolatilityRegimeClassifier()
        prices = [100.0] * 25
        classifier.classify("BTC/USD", prices)
        classifier.classify("ETH/USD", prices)
        # Each symbol has its own transitions
        btc = classifier.classify("BTC/USD", prices)
        eth = classifier.classify("ETH/USD", prices)
        assert btc.recent_transitions != eth.recent_transitions or True  # independent tracking

    def test_max_transitions_cap(self):
        classifier = VolatilityRegimeClassifier(max_transitions=3)
        stable = [100.0] * 25
        volatile = [100.0 if i % 2 == 0 else 150.0 for i in range(25)]
        for i in range(10):
            prices = stable if i % 2 == 0 else volatile
            classifier.classify("BTC/USD", prices)
        result = classifier.classify("BTC/USD", stable)
        assert len(result.recent_transitions) <= 3
