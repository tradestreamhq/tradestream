"""Tests for A/B model testing module."""

import pytest

from services.model_router.ab_testing import ABTestManager, Experiment


class TestExperiment:
    def test_should_shadow_respects_traffic_pct(self):
        exp = Experiment(
            experiment_id="test",
            agent_type="signal-generator",
            primary_model="a",
            challenger_model="b",
            traffic_pct=1.0,
            max_runs=10,
        )
        assert exp.should_shadow() is True

    def test_should_shadow_zero_traffic_never(self):
        exp = Experiment(
            experiment_id="test",
            agent_type="signal-generator",
            primary_model="a",
            challenger_model="b",
            traffic_pct=0.001,
            max_runs=10,
        )
        # With very low traffic, at least some should be False in 100 tries
        results = [exp.should_shadow() for _ in range(100)]
        assert not all(results)

    def test_complete_after_max_runs(self):
        exp = Experiment(
            experiment_id="test",
            agent_type="signal-generator",
            primary_model="a",
            challenger_model="b",
            traffic_pct=1.0,
            max_runs=2,
        )
        from services.model_router.ab_testing import ExperimentResult

        for _ in range(2):
            exp.record(
                ExperimentResult(
                    experiment_id="test",
                    agent_type="signal-generator",
                    primary_model="a",
                    challenger_model="b",
                    primary_latency_ms=100,
                    challenger_latency_ms=120,
                    primary_tokens=500,
                    challenger_tokens=480,
                )
            )
        assert exp.complete is True
        assert exp.active is False
        assert exp.should_shadow() is False

    def test_summary_empty(self):
        exp = Experiment(
            experiment_id="test",
            agent_type="x",
            primary_model="a",
            challenger_model="b",
            traffic_pct=0.5,
        )
        s = exp.summary()
        assert s["runs"] == 0
        assert s["active"] is True

    def test_summary_with_results(self):
        exp = Experiment(
            experiment_id="test",
            agent_type="x",
            primary_model="a",
            challenger_model="b",
            traffic_pct=0.5,
            max_runs=100,
        )
        from services.model_router.ab_testing import ExperimentResult

        exp.record(
            ExperimentResult(
                experiment_id="test",
                agent_type="x",
                primary_model="a",
                challenger_model="b",
                primary_latency_ms=100,
                challenger_latency_ms=200,
                primary_tokens=500,
                challenger_tokens=600,
            )
        )
        s = exp.summary()
        assert s["runs"] == 1
        assert s["primary_avg_latency_ms"] == 100
        assert s["challenger_avg_latency_ms"] == 200


class TestABTestManager:
    def test_create_experiment(self):
        mgr = ABTestManager()
        exp = mgr.create_experiment(
            experiment_id="exp1",
            agent_type="signal-generator",
            primary_model="google/gemini-3.0-flash",
            challenger_model="google/gemini-3.0-pro",
            traffic_pct=0.1,
        )
        assert exp.experiment_id == "exp1"
        assert exp.active is True

    def test_create_duplicate_raises(self):
        mgr = ABTestManager()
        mgr.create_experiment("exp1", "x", "a", "b")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_experiment("exp1", "x", "a", "b")

    def test_create_invalid_traffic_raises(self):
        mgr = ABTestManager()
        with pytest.raises(ValueError, match="traffic_pct"):
            mgr.create_experiment("exp1", "x", "a", "b", traffic_pct=0.0)
        with pytest.raises(ValueError, match="traffic_pct"):
            mgr.create_experiment("exp2", "x", "a", "b", traffic_pct=1.5)

    def test_get_active_for_agent(self):
        mgr = ABTestManager()
        mgr.create_experiment("exp1", "signal-generator", "a", "b")
        mgr.create_experiment("exp2", "janitor", "c", "d")
        exp = mgr.get_active_for_agent("signal-generator")
        assert exp is not None
        assert exp.experiment_id == "exp1"

    def test_get_active_for_agent_none(self):
        mgr = ABTestManager()
        assert mgr.get_active_for_agent("signal-generator") is None

    def test_stop_experiment(self):
        mgr = ABTestManager()
        mgr.create_experiment("exp1", "x", "a", "b")
        assert mgr.stop_experiment("exp1") is True
        assert mgr.get_experiment("exp1").active is False

    def test_stop_nonexistent(self):
        mgr = ABTestManager()
        assert mgr.stop_experiment("nope") is False

    def test_list_experiments(self):
        mgr = ABTestManager()
        mgr.create_experiment("exp1", "x", "a", "b")
        mgr.create_experiment("exp2", "y", "c", "d")
        summaries = mgr.list_experiments()
        assert len(summaries) == 2

    def test_record_result(self):
        mgr = ABTestManager()
        mgr.create_experiment("exp1", "x", "a", "b", max_runs=5)
        result = mgr.record_result(
            experiment_id="exp1",
            agent_type="x",
            primary_model="a",
            challenger_model="b",
            primary_latency_ms=100,
            challenger_latency_ms=150,
            primary_tokens=500,
            challenger_tokens=520,
        )
        assert result is not None
        assert mgr.get_experiment("exp1").runs == 1

    def test_record_result_inactive(self):
        mgr = ABTestManager()
        mgr.create_experiment("exp1", "x", "a", "b")
        mgr.stop_experiment("exp1")
        result = mgr.record_result("exp1", "x", "a", "b", 100, 150, 500, 520)
        assert result is None

    def test_record_result_nonexistent(self):
        mgr = ABTestManager()
        result = mgr.record_result("nope", "x", "a", "b", 100, 150, 500, 520)
        assert result is None
