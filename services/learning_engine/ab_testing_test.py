"""Tests for the A/B Testing module."""

import math
from unittest import mock

import pytest

from services.learning_engine.ab_testing import ABTestManager


class TestComputeVariantMetrics:
    def setup_method(self):
        self.manager = ABTestManager()

    def test_empty_observations(self):
        metrics = self.manager._compute_variant_metrics([])
        assert metrics["count"] == 0
        assert metrics["avg_pnl"] is None

    def test_positive_observations(self):
        obs = [
            {"pnl_percent": 2.0},
            {"pnl_percent": 3.0},
            {"pnl_percent": 1.0},
        ]
        metrics = self.manager._compute_variant_metrics(obs)
        assert metrics["count"] == 3
        assert metrics["avg_pnl"] == 2.0
        assert metrics["total_pnl"] == 6.0
        assert metrics["win_rate"] == 1.0

    def test_mixed_observations(self):
        obs = [
            {"pnl_percent": 5.0},
            {"pnl_percent": -3.0},
            {"pnl_percent": 2.0},
            {"pnl_percent": -1.0},
            {"pnl_percent": 4.0},
        ]
        metrics = self.manager._compute_variant_metrics(obs)
        assert metrics["count"] == 5
        assert metrics["win_rate"] == 0.6
        assert metrics["sharpe"] is not None

    def test_none_pnl_filtered(self):
        obs = [{"pnl_percent": 2.0}, {"pnl_percent": None}]
        metrics = self.manager._compute_variant_metrics(obs)
        assert metrics["count"] == 1


class TestCalculateImprovement:
    def setup_method(self):
        self.manager = ABTestManager()

    def test_positive_improvement(self):
        control = {"avg_pnl": 1.0}
        treatment = {"avg_pnl": 1.5}
        improvement = self.manager._calculate_improvement(control, treatment)
        assert improvement == 0.5

    def test_negative_improvement(self):
        control = {"avg_pnl": 2.0}
        treatment = {"avg_pnl": 1.0}
        improvement = self.manager._calculate_improvement(control, treatment)
        assert improvement == -0.5

    def test_none_values(self):
        assert self.manager._calculate_improvement({"avg_pnl": None}, {"avg_pnl": 1.0}) is None
        assert self.manager._calculate_improvement({"avg_pnl": 1.0}, {"avg_pnl": None}) is None

    def test_zero_control(self):
        assert self.manager._calculate_improvement({"avg_pnl": 0.0}, {"avg_pnl": 1.0}) is None


class TestCheckSignificance:
    def setup_method(self):
        self.manager = ABTestManager()

    def test_insufficient_data(self):
        control = [{"pnl_percent": 1.0}] * 3
        treatment = [{"pnl_percent": 2.0}] * 3
        assert self.manager._check_significance(control, treatment) is False

    def test_clearly_different(self):
        control = [{"pnl_percent": v} for v in [1.0, 1.1, 0.9, 1.0, 1.1, 0.9, 1.0]]
        treatment = [{"pnl_percent": v} for v in [5.0, 5.1, 4.9, 5.0, 5.1, 4.9, 5.0]]
        assert self.manager._check_significance(control, treatment) is True

    def test_not_different(self):
        control = [{"pnl_percent": v} for v in [1.0, 2.0, 3.0, 0.5, 2.5]]
        treatment = [{"pnl_percent": v} for v in [1.1, 1.9, 3.1, 0.6, 2.4]]
        assert self.manager._check_significance(control, treatment) is False

    def test_zero_variance(self):
        control = [{"pnl_percent": 1.0}] * 5
        treatment = [{"pnl_percent": 1.0}] * 5
        assert self.manager._check_significance(control, treatment) is False


class TestEvaluateExperiment:
    def test_evaluate_without_db(self):
        manager = ABTestManager()
        result = manager.evaluate_experiment("exp-1")
        assert result["recommendation"] == "insufficient_data"
        assert result["total_observations"] == 0

    def test_evaluate_with_mocked_data(self):
        manager = ABTestManager()

        # Mock _get_observations
        def mock_get(exp_id, variant):
            if variant == "control":
                return [{"pnl_percent": v} for v in [1.0, 0.5, 1.5, 0.8, 1.2]]
            return [{"pnl_percent": v} for v in [3.0, 2.5, 3.5, 2.8, 3.2]]

        manager._get_observations = mock_get

        result = manager.evaluate_experiment("exp-1")
        assert result["treatment"]["avg_pnl"] > result["control"]["avg_pnl"]
        assert result["improvement"] > 0
        assert result["recommendation"] in ("adopt_treatment", "continue_testing")


class TestCreateExperiment:
    def test_create_without_db(self):
        manager = ABTestManager()
        exp = manager.create_experiment(
            "spec-1", "BTC-USD",
            {"stop_loss": 2.0}, {"stop_loss": 3.0},
            hypothesis="Wider stops improve volatile market performance",
        )
        assert exp["id"] is not None
        assert exp["status"] == "running"

    def test_create_with_db(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        manager = ABTestManager(db_connection=conn)
        exp = manager.create_experiment(
            "spec-1", "BTC-USD",
            {"stop_loss": 2.0}, {"stop_loss": 3.0},
        )
        cur.execute.assert_called_once()
        conn.commit.assert_called_once()


class TestRecordObservation:
    def test_record_without_db(self):
        manager = ABTestManager()
        obs_id = manager.record_observation("exp-1", "control", 2.5)
        assert obs_id is not None

    def test_record_with_db(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        manager = ABTestManager(db_connection=conn)
        manager.record_observation("exp-1", "treatment", 3.5,
                                    pnl_absolute=350, signal_type="BUY")
        cur.execute.assert_called_once()
        conn.commit.assert_called_once()


class TestGetRunningExperiments:
    def test_no_connection(self):
        manager = ABTestManager()
        assert manager.get_running_experiments() == []
