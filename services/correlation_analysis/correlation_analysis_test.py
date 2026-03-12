"""Tests for correlation analysis service."""

import numpy as np
import pytest

from services.correlation_analysis.correlation_analysis import (
    CorrelationAlert,
    CorrelationAnalysisResult,
    CorrelationCluster,
    CorrelationRegimeChange,
    DiversificationRecommendation,
    check_portfolio_correlation_alerts,
    compute_correlation_matrix,
    compute_rolling_correlation,
    detect_regime_changes,
    generate_recommendations,
    identify_correlated_clusters,
    run_correlation_analysis,
)


def _make_correlated_returns(n: int, correlation: float, seed: int = 42) -> tuple:
    """Generate two correlated return series."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.02, n)
    noise = rng.normal(0, 0.02, n)
    y = correlation * x + np.sqrt(1 - correlation**2) * noise
    return x, y


def _make_uncorrelated_returns(n: int, seed: int = 42) -> tuple:
    """Generate two uncorrelated return series."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.02, n)
    y = rng.normal(0, 0.02, n)
    return x, y


class TestComputeRollingCorrelation:
    def test_perfectly_correlated(self):
        x = np.array([0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02, 0.01, -0.01])
        y = x * 2  # Perfectly correlated
        result = compute_rolling_correlation(x, y, window=5)
        assert len(result) == 6
        for corr in result:
            assert abs(corr - 1.0) < 1e-10

    def test_perfectly_anticorrelated(self):
        x = np.array([0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02, 0.01, -0.01])
        y = -x
        result = compute_rolling_correlation(x, y, window=5)
        for corr in result:
            assert abs(corr - (-1.0)) < 1e-10

    def test_window_larger_than_data(self):
        x = np.array([0.01, -0.02, 0.03])
        y = np.array([0.02, -0.01, 0.04])
        result = compute_rolling_correlation(x, y, window=5)
        assert len(result) == 0

    def test_constant_series_returns_zero(self):
        x = np.ones(10) * 0.01
        y = np.array([0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02, 0.01, -0.01])
        result = compute_rolling_correlation(x, y, window=5)
        for corr in result:
            assert corr == 0.0

    def test_window_of_one_returns_empty(self):
        x = np.array([0.01, 0.02])
        y = np.array([0.03, 0.04])
        result = compute_rolling_correlation(x, y, window=1)
        assert len(result) == 0


class TestComputeCorrelationMatrix:
    def test_two_correlated_assets(self):
        x, y = _make_correlated_returns(100, 0.9)
        returns = {"BTC-USD": x, "ETH-USD": y}
        matrix = compute_correlation_matrix(returns, lookback=50)

        assert matrix["BTC-USD"]["BTC-USD"] == 1.0
        assert matrix["ETH-USD"]["ETH-USD"] == 1.0
        # High correlation should be detected
        assert matrix["BTC-USD"]["ETH-USD"] > 0.7
        # Symmetry
        assert matrix["BTC-USD"]["ETH-USD"] == matrix["ETH-USD"]["BTC-USD"]

    def test_uncorrelated_assets(self):
        x, y = _make_uncorrelated_returns(200)
        returns = {"BTC-USD": x, "SOL-USD": y}
        matrix = compute_correlation_matrix(returns, lookback=100)

        # Uncorrelated assets should have low absolute correlation
        assert abs(matrix["BTC-USD"]["SOL-USD"]) < 0.3

    def test_single_asset(self):
        returns = {"BTC-USD": np.random.default_rng(42).normal(0, 0.02, 50)}
        matrix = compute_correlation_matrix(returns, lookback=30)
        assert matrix["BTC-USD"]["BTC-USD"] == 1.0

    def test_short_series(self):
        returns = {"A": np.array([0.01, 0.02]), "B": np.array([0.03, 0.04])}
        matrix = compute_correlation_matrix(returns, lookback=30)
        # Too short for meaningful correlation, should return 0
        assert matrix["A"]["B"] == 0.0

    def test_multiple_assets(self):
        rng = np.random.default_rng(42)
        base = rng.normal(0, 0.02, 100)
        returns = {
            "A": base,
            "B": base + rng.normal(0, 0.005, 100),
            "C": rng.normal(0, 0.02, 100),
        }
        matrix = compute_correlation_matrix(returns, lookback=50)

        # A and B should be highly correlated
        assert matrix["A"]["B"] > 0.7
        # A and C should be less correlated
        assert abs(matrix["A"]["C"]) < matrix["A"]["B"]


class TestDetectRegimeChanges:
    def test_detects_correlation_breakdown(self):
        """Simulate correlation that is high historically but breaks down recently."""
        rng = np.random.default_rng(42)
        n = 120

        # First 90 periods: highly correlated
        base_early = rng.normal(0, 0.02, 90)
        a_early = base_early
        b_early = 0.95 * base_early + 0.05 * rng.normal(0, 0.02, 90)

        # Last 30 periods: uncorrelated
        a_late = rng.normal(0, 0.02, 30)
        b_late = rng.normal(0, 0.02, 30)

        returns = {
            "BTC-USD": np.concatenate([a_early, a_late]),
            "ETH-USD": np.concatenate([b_early, b_late]),
        }

        changes = detect_regime_changes(
            returns, short_lookback=30, long_lookback=90, threshold=0.3
        )

        assert len(changes) >= 1
        change = changes[0]
        assert change.asset_a == "BTC-USD"
        assert change.asset_b == "ETH-USD"
        assert change.is_significant
        # Current should be much lower than historical
        assert change.current_correlation < change.previous_correlation

    def test_stable_correlation_no_changes(self):
        """Stable correlation should not trigger regime change."""
        x, y = _make_correlated_returns(120, 0.8)
        returns = {"A": x, "B": y}

        changes = detect_regime_changes(
            returns, short_lookback=30, long_lookback=90, threshold=0.3
        )
        assert len(changes) == 0

    def test_empty_returns(self):
        changes = detect_regime_changes({}, short_lookback=30, long_lookback=90)
        assert changes == []

    def test_single_asset_no_changes(self):
        returns = {"A": np.random.default_rng(42).normal(0, 0.02, 120)}
        changes = detect_regime_changes(returns, short_lookback=30, long_lookback=90)
        assert changes == []


class TestIdentifyCorrelatedClusters:
    def test_two_correlated_assets_form_cluster(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.9, "C": 0.1},
            "B": {"A": 0.9, "B": 1.0, "C": 0.2},
            "C": {"A": 0.1, "B": 0.2, "C": 1.0},
        }
        clusters = identify_correlated_clusters(matrix, threshold=0.7)
        assert len(clusters) == 1
        assert set(clusters[0].assets) == {"A", "B"}
        assert clusters[0].avg_intra_correlation >= 0.9

    def test_no_clusters_when_uncorrelated(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.1, "C": 0.2},
            "B": {"A": 0.1, "B": 1.0, "C": 0.15},
            "C": {"A": 0.2, "B": 0.15, "C": 1.0},
        }
        clusters = identify_correlated_clusters(matrix, threshold=0.7)
        assert len(clusters) == 0

    def test_three_assets_in_one_cluster(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.85, "C": 0.80},
            "B": {"A": 0.85, "B": 1.0, "C": 0.82},
            "C": {"A": 0.80, "B": 0.82, "C": 1.0},
        }
        clusters = identify_correlated_clusters(matrix, threshold=0.7)
        assert len(clusters) == 1
        assert set(clusters[0].assets) == {"A", "B", "C"}

    def test_two_separate_clusters(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.9, "C": 0.1, "D": 0.0},
            "B": {"A": 0.9, "B": 1.0, "C": 0.1, "D": 0.05},
            "C": {"A": 0.1, "B": 0.1, "C": 1.0, "D": 0.85},
            "D": {"A": 0.0, "B": 0.05, "C": 0.85, "D": 1.0},
        }
        clusters = identify_correlated_clusters(matrix, threshold=0.7)
        assert len(clusters) == 2


class TestGenerateRecommendations:
    def test_high_correlation_pair_in_portfolio(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.92},
            "B": {"A": 0.92, "B": 1.0},
        }
        recs = generate_recommendations(
            matrix, clusters=[], regime_changes=[], portfolio_symbols=["A", "B"]
        )
        assert len(recs) >= 1
        assert recs[0].severity == "high"
        assert "A" in recs[0].affected_assets
        assert "B" in recs[0].affected_assets

    def test_no_recommendations_for_uncorrelated_portfolio(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.1},
            "B": {"A": 0.1, "B": 1.0},
        }
        recs = generate_recommendations(
            matrix, clusters=[], regime_changes=[], portfolio_symbols=["A", "B"]
        )
        assert len(recs) == 0

    def test_cluster_warning(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.85, "C": 0.1},
            "B": {"A": 0.85, "B": 1.0, "C": 0.2},
            "C": {"A": 0.1, "B": 0.2, "C": 1.0},
        }
        clusters = [CorrelationCluster(assets=["A", "B"], avg_intra_correlation=0.85)]
        recs = generate_recommendations(
            matrix,
            clusters=clusters,
            regime_changes=[],
            portfolio_symbols=["A", "B", "C"],
        )
        # Should have both a high-corr pair warning and a cluster warning
        assert any("cluster" in r.message.lower() for r in recs)

    def test_regime_change_warning(self):
        matrix = {"A": {"A": 1.0, "B": 0.1}, "B": {"A": 0.1, "B": 1.0}}
        changes = [
            CorrelationRegimeChange(
                asset_a="A",
                asset_b="B",
                previous_correlation=0.2,
                current_correlation=0.7,
                change=0.5,
                is_significant=True,
            )
        ]
        recs = generate_recommendations(
            matrix,
            clusters=[],
            regime_changes=changes,
            portfolio_symbols=["A"],
        )
        assert any("regime" in r.message.lower() for r in recs)

    def test_non_portfolio_assets_ignored(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.95},
            "B": {"A": 0.95, "B": 1.0},
        }
        # Neither A nor B is in portfolio
        recs = generate_recommendations(
            matrix, clusters=[], regime_changes=[], portfolio_symbols=["C"]
        )
        assert len(recs) == 0


class TestCheckPortfolioCorrelationAlerts:
    def test_high_avg_correlation_alert(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.85, "C": 0.80},
            "B": {"A": 0.85, "B": 1.0, "C": 0.75},
            "C": {"A": 0.80, "B": 0.75, "C": 1.0},
        }
        alerts = check_portfolio_correlation_alerts(
            matrix, ["A", "B", "C"], alert_threshold=0.6
        )
        assert len(alerts) >= 1
        assert alerts[0].metric == "avg_pairwise_correlation"
        assert alerts[0].value > 0.6

    def test_no_alert_when_below_threshold(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.1},
            "B": {"A": 0.1, "B": 1.0},
        }
        alerts = check_portfolio_correlation_alerts(
            matrix, ["A", "B"], alert_threshold=0.6
        )
        assert len(alerts) == 0

    def test_single_asset_no_alert(self):
        matrix = {"A": {"A": 1.0}}
        alerts = check_portfolio_correlation_alerts(matrix, ["A"])
        assert len(alerts) == 0

    def test_near_perfect_correlation_alert(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.98},
            "B": {"A": 0.98, "B": 1.0},
        }
        alerts = check_portfolio_correlation_alerts(
            matrix, ["A", "B"], alert_threshold=0.6
        )
        # Should have both avg and max alerts
        assert len(alerts) == 2
        metrics = {a.metric for a in alerts}
        assert "avg_pairwise_correlation" in metrics
        assert "max_pairwise_correlation" in metrics


class TestRunCorrelationAnalysis:
    def test_full_analysis_with_correlated_data(self):
        rng = np.random.default_rng(42)
        base = rng.normal(0, 0.02, 120)

        returns = {
            "BTC-USD": base,
            "ETH-USD": 0.9 * base + 0.1 * rng.normal(0, 0.02, 120),
            "SOL-USD": rng.normal(0, 0.02, 120),
        }
        portfolio = ["BTC-USD", "ETH-USD", "SOL-USD"]

        result = run_correlation_analysis(
            returns,
            portfolio_symbols=portfolio,
            short_lookback=30,
            long_lookback=90,
        )

        assert isinstance(result, CorrelationAnalysisResult)
        # BTC and ETH should be correlated
        assert result.correlation_matrix["BTC-USD"]["ETH-USD"] > 0.7
        # SOL should be less correlated with BTC
        assert (
            abs(result.correlation_matrix["BTC-USD"]["SOL-USD"])
            < result.correlation_matrix["BTC-USD"]["ETH-USD"]
        )
        # Should have at least one cluster (BTC+ETH)
        assert len(result.clusters) >= 1
        # Should have recommendations about BTC/ETH correlation
        assert len(result.recommendations) >= 1

    def test_full_analysis_with_uncorrelated_data(self):
        rng = np.random.default_rng(42)
        returns = {
            "A": rng.normal(0, 0.02, 120),
            "B": rng.normal(0, 0.02, 120),
            "C": rng.normal(0, 0.02, 120),
        }
        result = run_correlation_analysis(returns, portfolio_symbols=["A", "B", "C"])

        assert len(result.clusters) == 0
        assert len(result.alerts) == 0

    def test_configurable_thresholds(self):
        x, y = _make_correlated_returns(120, 0.8)
        returns = {"A": x, "B": y}

        # With low threshold, should detect cluster
        result_low = run_correlation_analysis(
            returns,
            portfolio_symbols=["A", "B"],
            correlation_threshold=0.5,
        )
        # With very high threshold, might not
        result_high = run_correlation_analysis(
            returns,
            portfolio_symbols=["A", "B"],
            correlation_threshold=0.99,
        )

        assert len(result_low.clusters) >= len(result_high.clusters)
