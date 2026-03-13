"""Tests for the Correlation Engine core logic."""

import numpy as np
import pandas as pd
import pytest

from services.correlation_engine.engine import (
    PairAnalysis,
    analyze_pair,
    compute_spread,
    compute_zscore,
    correlation_matrix,
    engle_granger_test,
    find_cointegrated_pairs,
    rolling_correlation,
)


class TestRollingCorrelation:
    def test_perfectly_correlated(self):
        """Two identical series should have correlation of 1.0."""
        s1 = pd.Series(range(50), dtype=float)
        s2 = pd.Series(range(50), dtype=float)
        result = rolling_correlation(s1, s2, window=10)
        # After warm-up, all values should be 1.0
        valid = result.dropna()
        assert len(valid) > 0
        np.testing.assert_allclose(valid.values, 1.0, atol=1e-10)

    def test_perfectly_anticorrelated(self):
        """Negatively correlated series should have correlation of -1.0."""
        s1 = pd.Series(range(50), dtype=float)
        s2 = pd.Series([-x for x in range(50)], dtype=float)
        result = rolling_correlation(s1, s2, window=10)
        valid = result.dropna()
        np.testing.assert_allclose(valid.values, -1.0, atol=1e-10)

    def test_uncorrelated(self):
        """Orthogonal series should have near-zero correlation."""
        np.random.seed(42)
        s1 = pd.Series(np.random.randn(1000))
        s2 = pd.Series(np.random.randn(1000))
        result = rolling_correlation(s1, s2, window=100)
        valid = result.dropna()
        assert abs(valid.mean()) < 0.15

    def test_window_size_respected(self):
        """NaN count should equal window - 1."""
        s1 = pd.Series(range(50), dtype=float)
        s2 = pd.Series(range(50), dtype=float)
        window = 20
        result = rolling_correlation(s1, s2, window=window)
        assert result.isna().sum() == window - 1


class TestCorrelationMatrix:
    def test_diagonal_is_one(self):
        """Diagonal of correlation matrix should be 1.0."""
        df = pd.DataFrame({
            "A": np.random.randn(100),
            "B": np.random.randn(100),
            "C": np.random.randn(100),
        })
        matrix = correlation_matrix(df)
        np.testing.assert_allclose(np.diag(matrix.values), 1.0)

    def test_symmetric(self):
        """Correlation matrix should be symmetric."""
        np.random.seed(42)
        df = pd.DataFrame({
            "A": np.random.randn(100),
            "B": np.random.randn(100),
        })
        matrix = correlation_matrix(df)
        np.testing.assert_allclose(matrix.values, matrix.values.T)

    def test_known_correlation(self):
        """Series with known linear relationship should have high correlation."""
        np.random.seed(42)
        x = np.random.randn(200)
        df = pd.DataFrame({
            "X": x,
            "Y": 2 * x + 0.1 * np.random.randn(200),  # Strong linear relation
        })
        matrix = correlation_matrix(df)
        assert matrix.loc["X", "Y"] > 0.95


class TestEngleGranger:
    def test_cointegrated_pair(self):
        """Two series with shared stochastic trend should be cointegrated."""
        np.random.seed(42)
        n = 500
        # Shared random walk
        common = np.cumsum(np.random.randn(n))
        s1 = common + np.random.randn(n) * 0.5
        s2 = 0.8 * common + np.random.randn(n) * 0.5

        cointegrated, p_value, hedge_ratio = engle_granger_test(s1, s2)
        assert cointegrated is True
        assert p_value < 0.05

    def test_non_cointegrated_pair(self):
        """Two independent random walks should not be cointegrated."""
        np.random.seed(42)
        n = 500
        s1 = np.cumsum(np.random.randn(n))
        s2 = np.cumsum(np.random.randn(n))

        cointegrated, p_value, _ = engle_granger_test(s1, s2)
        assert cointegrated is False
        assert p_value >= 0.05


class TestSpreadAndZscore:
    def test_spread_calculation(self):
        """Spread should equal series1 - hedge_ratio * series2."""
        s1 = np.array([100.0, 102.0, 101.0, 103.0])
        s2 = np.array([50.0, 51.0, 50.5, 51.5])
        hedge_ratio = 2.0
        spread = compute_spread(s1, s2, hedge_ratio)
        expected = s1 - 2.0 * s2
        np.testing.assert_allclose(spread, expected)

    def test_zscore_mean_reversion(self):
        """Z-score of a mean-reverting spread should be bounded."""
        np.random.seed(42)
        spread = np.random.randn(200)  # Mean-reverting by construction
        zscores = compute_zscore(spread, window=30)
        valid = zscores[~np.isnan(zscores)]
        assert abs(np.mean(valid)) < 1.0
        assert np.std(valid) < 2.0

    def test_zscore_window_nans(self):
        """First window-1 values should be NaN."""
        spread = np.random.randn(50)
        window = 20
        zscores = compute_zscore(spread, window=window)
        assert np.all(np.isnan(zscores[: window - 1]))


class TestAnalyzePair:
    def test_returns_pair_analysis(self):
        """analyze_pair should return a PairAnalysis with all fields."""
        np.random.seed(42)
        n = 200
        common = np.cumsum(np.random.randn(n))
        s1 = common + np.random.randn(n) * 0.3
        s2 = 0.5 * common + np.random.randn(n) * 0.3

        result = analyze_pair("BTC/USD", "ETH/USD", s1, s2)
        assert isinstance(result, PairAnalysis)
        assert result.pair1 == "BTC/USD"
        assert result.pair2 == "ETH/USD"
        assert -1.0 <= result.correlation <= 1.0
        assert isinstance(result.cointegrated, bool)
        assert result.spread_std > 0

    def test_identical_series(self):
        """Identical series should have correlation ~1 and hedge ratio ~1."""
        prices = np.cumsum(np.random.randn(200)) + 100
        result = analyze_pair("A", "B", prices, prices)
        assert result.correlation > 0.999


class TestFindCointegratedPairs:
    def test_finds_cointegrated(self):
        """Should find pairs that share a common stochastic trend."""
        np.random.seed(42)
        n = 500
        common = np.cumsum(np.random.randn(n))
        df = pd.DataFrame({
            "A": common + np.random.randn(n) * 0.3,
            "B": 0.7 * common + np.random.randn(n) * 0.3,
            "C": np.cumsum(np.random.randn(n)),  # Independent
        })
        pairs = find_cointegrated_pairs(df, significance=0.05)
        # A and B should be cointegrated
        pair_names = [(p.pair1, p.pair2) for p in pairs]
        assert ("A", "B") in pair_names

    def test_empty_on_independent(self):
        """Independent random walks should yield no cointegrated pairs."""
        np.random.seed(42)
        n = 500
        df = pd.DataFrame({
            "X": np.cumsum(np.random.randn(n)),
            "Y": np.cumsum(np.random.randn(n)),
        })
        pairs = find_cointegrated_pairs(df, significance=0.05)
        assert len(pairs) == 0

    def test_too_short_series_skipped(self):
        """Series shorter than 30 points should be skipped."""
        df = pd.DataFrame({
            "A": np.random.randn(20),
            "B": np.random.randn(20),
        })
        pairs = find_cointegrated_pairs(df)
        assert len(pairs) == 0
