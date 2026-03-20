"""Tests for the Strategy Weight Optimizer."""

from unittest import mock

import pytest

from services.learning_engine.weight_optimizer import (
    DEFAULT_CONFIG,
    WeightOptimizer,
)


class TestScoreStrategy:
    def setup_method(self):
        self.optimizer = WeightOptimizer()

    def test_high_performer(self):
        perf = {"sharpe_ratio": 2.5, "win_rate": 0.7, "avg_pnl_percent": 3.0}
        score = self.optimizer._score_strategy(perf)
        assert score > 0.5

    def test_low_performer(self):
        perf = {"sharpe_ratio": -1.0, "win_rate": 0.3, "avg_pnl_percent": -2.0}
        score = self.optimizer._score_strategy(perf)
        assert score < 0.5

    def test_none_values(self):
        perf = {"sharpe_ratio": None, "win_rate": None, "avg_pnl_percent": None}
        score = self.optimizer._score_strategy(perf)
        assert score >= 0.0

    def test_extreme_sharpe(self):
        perf = {"sharpe_ratio": 10.0, "win_rate": 1.0, "avg_pnl_percent": 10.0}
        score = self.optimizer._score_strategy(perf)
        assert score <= 1.0


class TestNormalizeToWeights:
    def setup_method(self):
        self.optimizer = WeightOptimizer()

    def test_normalize_single_strategy(self):
        scored = [{"strategy_spec_id": "s1", "score": 0.5, "has_data": True}]
        weights = self.optimizer._normalize_to_weights(scored)
        assert len(weights) == 1
        assert weights[0]["weight"] == 1.0  # single strategy = average

    def test_normalize_multiple(self):
        scored = [
            {"strategy_spec_id": "s1", "score": 0.8, "has_data": True},
            {"strategy_spec_id": "s2", "score": 0.4, "has_data": True},
        ]
        weights = self.optimizer._normalize_to_weights(scored)
        assert len(weights) == 2
        # Higher score should get higher weight
        w_map = {w["strategy_spec_id"]: w["weight"] for w in weights}
        assert w_map["s1"] > w_map["s2"]

    def test_no_data_gets_default(self):
        scored = [{"strategy_spec_id": "s1", "score": 0.0, "has_data": False}]
        weights = self.optimizer._normalize_to_weights(scored)
        assert weights[0]["weight"] == DEFAULT_CONFIG["default_weight"]

    def test_weight_bounds(self):
        scored = [
            {"strategy_spec_id": "s1", "score": 10.0, "has_data": True},
            {"strategy_spec_id": "s2", "score": 0.001, "has_data": True},
        ]
        weights = self.optimizer._normalize_to_weights(scored)
        for w in weights:
            assert w["weight"] >= DEFAULT_CONFIG["min_weight"]
            assert w["weight"] <= DEFAULT_CONFIG["max_weight"]


class TestOptimizeWeights:
    def test_optimize_empty(self):
        optimizer = WeightOptimizer()
        result = optimizer.optimize_weights([], "trending_up", "BTC-USD")
        assert result == []

    def test_optimize_with_data(self):
        optimizer = WeightOptimizer()
        perfs = [
            {
                "strategy_spec_id": "s1",
                "sharpe_ratio": 2.0,
                "win_rate": 0.65,
                "avg_pnl_percent": 2.5,
                "trade_count": 20,
            },
            {
                "strategy_spec_id": "s2",
                "sharpe_ratio": -0.5,
                "win_rate": 0.35,
                "avg_pnl_percent": -1.0,
                "trade_count": 15,
            },
        ]
        result = optimizer.optimize_weights(perfs, "volatile", "BTC-USD")
        assert len(result) == 2
        w_map = {r["strategy_spec_id"]: r["weight"] for r in result}
        assert w_map["s1"] > w_map["s2"]

    def test_optimize_insufficient_trades(self):
        optimizer = WeightOptimizer()
        perfs = [
            {
                "strategy_spec_id": "s1",
                "sharpe_ratio": 2.0,
                "win_rate": 0.65,
                "avg_pnl_percent": 2.5,
                "trade_count": 2,  # Below min_trades_required
            },
        ]
        result = optimizer.optimize_weights(perfs, "trending_up", "ETH-USD")
        assert len(result) == 1
        assert result[0]["weight"] == DEFAULT_CONFIG["default_weight"]


class TestSmoothing:
    def test_smoothing_blends(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)
        cur.description = [("strategy_spec_id",), ("weight",)]
        cur.fetchall.return_value = [("s1", 0.5)]

        optimizer = WeightOptimizer(db_connection=conn)
        new_weights = [{"strategy_spec_id": "s1", "weight": 2.0, "reason": "test"}]

        smoothed = optimizer._apply_smoothing(new_weights, "trending_up", "BTC-USD")
        assert len(smoothed) == 1
        # Smoothed should be between old (0.5) and new (2.0)
        assert 0.5 < smoothed[0]["weight"] < 2.0
        assert smoothed[0]["previous_weight"] == 0.5


class TestCustomConfig:
    def test_custom_min_trades(self):
        config = dict(DEFAULT_CONFIG)
        config["min_trades_required"] = 100
        optimizer = WeightOptimizer(config=config)

        perfs = [
            {
                "strategy_spec_id": "s1",
                "sharpe_ratio": 2.0,
                "win_rate": 0.65,
                "avg_pnl_percent": 2.5,
                "trade_count": 50,  # Below custom threshold
            },
        ]
        result = optimizer.optimize_weights(perfs, "trending_up", "BTC-USD")
        assert result[0]["weight"] == config["default_weight"]
