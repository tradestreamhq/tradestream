"""Tests for the validation phase."""

from unittest.mock import MagicMock, patch

from services.agent_orchestration import config
from services.agent_orchestration.validation import (
    _aggregate_metrics,
    _extract_metrics,
    _passes_minimum_criteria,
    validate_candidates,
)


class TestExtractMetrics:
    def test_extracts_all_fields(self):
        result = {
            "sharpe_ratio": 1.5,
            "win_rate": 0.55,
            "max_drawdown": -0.15,
            "cumulative_return": 0.3,
            "total_trades": 50,
            "profit_factor": 1.8,
            "sortino_ratio": 2.0,
        }
        metrics = _extract_metrics(result)
        assert metrics["sharpe_ratio"] == 1.5
        assert metrics["total_trades"] == 50

    def test_handles_none(self):
        assert _extract_metrics(None) is None

    def test_handles_empty_dict(self):
        metrics = _extract_metrics({})
        assert metrics is not None
        assert metrics["sharpe_ratio"] == 0.0


class TestPassesMinimumCriteria:
    def test_passing_metrics(self):
        metrics = {
            "sharpe_ratio": 1.0,
            "win_rate": 0.55,
            "max_drawdown": -0.10,
            "total_trades": 20,
        }
        assert _passes_minimum_criteria(metrics) is True

    def test_low_sharpe(self):
        metrics = {
            "sharpe_ratio": 0.1,
            "win_rate": 0.55,
            "max_drawdown": -0.10,
            "total_trades": 20,
        }
        assert _passes_minimum_criteria(metrics) is False

    def test_low_win_rate(self):
        metrics = {
            "sharpe_ratio": 1.0,
            "win_rate": 0.30,
            "max_drawdown": -0.10,
            "total_trades": 20,
        }
        assert _passes_minimum_criteria(metrics) is False

    def test_excessive_drawdown(self):
        metrics = {
            "sharpe_ratio": 1.0,
            "win_rate": 0.55,
            "max_drawdown": -0.50,
            "total_trades": 20,
        }
        assert _passes_minimum_criteria(metrics) is False

    def test_too_few_trades(self):
        metrics = {
            "sharpe_ratio": 1.0,
            "win_rate": 0.55,
            "max_drawdown": -0.10,
            "total_trades": 2,
        }
        assert _passes_minimum_criteria(metrics) is False

    def test_none_metrics(self):
        assert _passes_minimum_criteria(None) is False


class TestAggregateMetrics:
    def test_averages_correctly(self):
        symbol_metrics = {
            "BTC-USD": {
                "sharpe_ratio": 1.0,
                "win_rate": 0.6,
                "max_drawdown": -0.1,
                "cumulative_return": 0.2,
                "total_trades": 30,
                "profit_factor": 1.5,
                "sortino_ratio": 1.8,
            },
            "ETH-USD": {
                "sharpe_ratio": 2.0,
                "win_rate": 0.5,
                "max_drawdown": -0.2,
                "cumulative_return": 0.4,
                "total_trades": 20,
                "profit_factor": 2.0,
                "sortino_ratio": 2.5,
            },
        }
        agg = _aggregate_metrics(symbol_metrics)
        assert agg["sharpe_ratio"] == 1.5
        assert agg["win_rate"] == 0.55
        assert agg["total_trades"] == 50
        assert len(agg["symbols_tested"]) == 2


class TestValidateCandidates:
    @patch("services.agent_orchestration.validation._run_backtest")
    def test_filters_by_criteria(self, mock_backtest):
        good_result = {
            "sharpe_ratio": 1.5,
            "win_rate": 0.6,
            "max_drawdown": -0.1,
            "cumulative_return": 0.3,
            "total_trades": 30,
            "profit_factor": 1.8,
            "sortino_ratio": 2.0,
        }
        bad_result = {
            "sharpe_ratio": 0.1,
            "win_rate": 0.3,
            "max_drawdown": -0.5,
            "cumulative_return": -0.1,
            "total_trades": 5,
            "profit_factor": 0.5,
            "sortino_ratio": 0.2,
        }

        def side_effect(mcp_urls, name, symbol, period_days=90):
            if name == "good_strat":
                return good_result
            return bad_result

        mock_backtest.side_effect = side_effect
        mcp_urls = {
            "backtest": "http://localhost:8083",
            "strategy": "http://localhost:8080",
        }

        result = validate_candidates(["good_strat", "bad_strat"], mcp_urls)
        assert len(result) == 1
        assert result[0][0] == "good_strat"

    @patch("services.agent_orchestration.validation._run_backtest")
    def test_handles_backtest_failure(self, mock_backtest):
        mock_backtest.return_value = None
        mcp_urls = {
            "backtest": "http://localhost:8083",
            "strategy": "http://localhost:8080",
        }

        result = validate_candidates(["failing_strat"], mcp_urls)
        assert len(result) == 0

    @patch("services.agent_orchestration.validation._run_backtest")
    def test_sorts_by_sharpe(self, mock_backtest):
        def side_effect(mcp_urls, name, symbol, period_days=90):
            sharpe = 2.0 if name == "best" else 1.0
            return {
                "sharpe_ratio": sharpe,
                "win_rate": 0.6,
                "max_drawdown": -0.1,
                "cumulative_return": 0.3,
                "total_trades": 30,
                "profit_factor": 1.8,
                "sortino_ratio": 2.0,
            }

        mock_backtest.side_effect = side_effect
        mcp_urls = {
            "backtest": "http://localhost:8083",
            "strategy": "http://localhost:8080",
        }

        result = validate_candidates(["ok", "best"], mcp_urls)
        assert len(result) == 2
        assert result[0][0] == "best"
