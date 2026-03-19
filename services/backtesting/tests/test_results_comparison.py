"""Tests for Results Comparison (VectorBT vs Ta4j)."""

import pytest

from services.backtesting.vectorbt_runner import BacktestMetrics
from services.backtesting.results_comparison import (
    ComparisonResult,
    ResultsComparator,
)


def _make_metrics(**kwargs) -> BacktestMetrics:
    """Helper to create BacktestMetrics with defaults."""
    defaults = dict(
        cumulative_return=0.15,
        annualized_return=0.30,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=0.10,
        volatility=0.02,
        win_rate=0.55,
        profit_factor=1.8,
        number_of_trades=50,
        average_trade_duration=30.0,
        alpha=0.05,
        beta=0.9,
        strategy_score=0.75,
    )
    defaults.update(kwargs)
    return BacktestMetrics(**defaults)


class TestResultsComparator:
    def test_identical_results_match(self):
        """Test that identical results produce a match."""
        comparator = ResultsComparator()
        m = _make_metrics()
        result = comparator.compare("TEST_STRATEGY", m, m)

        assert result.overall_match is True
        assert result.match_ratio == 1.0
        for comp in result.metric_comparisons.values():
            assert comp.within_tolerance is True

    def test_different_results_mismatch(self):
        """Test that very different results produce a mismatch."""
        comparator = ResultsComparator()
        vbt = _make_metrics(cumulative_return=0.50, sharpe_ratio=3.0, win_rate=0.80)
        ta4j = _make_metrics(cumulative_return=-0.10, sharpe_ratio=-0.5, win_rate=0.30)

        result = comparator.compare("TEST_STRATEGY", vbt, ta4j)
        assert result.overall_match is False

    def test_close_results_match(self):
        """Test that close-but-not-identical results still match."""
        comparator = ResultsComparator()
        vbt = _make_metrics(cumulative_return=0.150, sharpe_ratio=1.50)
        ta4j = _make_metrics(cumulative_return=0.155, sharpe_ratio=1.52)

        result = comparator.compare("TEST_STRATEGY", vbt, ta4j)
        assert result.overall_match is True

    def test_comparison_has_all_metrics(self):
        """Test that all 13 metrics are compared."""
        comparator = ResultsComparator()
        m = _make_metrics()
        result = comparator.compare("TEST_STRATEGY", m, m)

        assert len(result.metric_comparisons) == 13

    def test_custom_tolerances(self):
        """Test custom tolerance values."""
        strict_tolerances = {k: 0.001 for k in ResultsComparator.DEFAULT_TOLERANCES}
        comparator = ResultsComparator(tolerances=strict_tolerances)

        vbt = _make_metrics(cumulative_return=0.150)
        ta4j = _make_metrics(cumulative_return=0.155)

        result = comparator.compare("TEST_STRATEGY", vbt, ta4j)
        # With very strict tolerances, even small differences fail
        cum_comp = result.metric_comparisons["cumulative_return"]
        assert cum_comp.within_tolerance is False

    def test_batch_comparison(self):
        """Test comparing multiple strategies at once."""
        comparator = ResultsComparator()
        m1 = _make_metrics()
        m2 = _make_metrics(cumulative_return=0.20)

        results = comparator.compare_batch({
            "STRATEGY_A": (m1, m1),
            "STRATEGY_B": (m2, _make_metrics(cumulative_return=-0.5)),
        })

        assert results["STRATEGY_A"].overall_match is True
        assert results["STRATEGY_B"].overall_match is False

    def test_summary_format(self):
        """Test that summary contains meaningful information."""
        comparator = ResultsComparator()
        m = _make_metrics()
        result = comparator.compare("TEST_STRATEGY", m, m)
        assert "MATCH" in result.summary
        assert "13/13" in result.summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
