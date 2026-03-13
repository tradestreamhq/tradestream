"""Tests for parameter grid generation and result ranking."""

import pytest

from services.optimization_api.optimization_service import (
    CategoricalParamSpace,
    NumericParamSpace,
    Objective,
    TrialResult,
    generate_param_grid,
    get_objective_value,
    rank_results,
    sample_random_params,
)


class TestGenerateParamGrid:
    def test_single_numeric_param(self):
        params = [NumericParamSpace(name="period", min=10, max=30, step=10)]
        grid = generate_param_grid(params, [])
        assert len(grid) == 3
        values = [g["period"] for g in grid]
        assert values == [10, 20, 30]

    def test_multiple_numeric_params(self):
        params = [
            NumericParamSpace(name="fast", min=5, max=15, step=5),
            NumericParamSpace(name="slow", min=20, max=30, step=10),
        ]
        grid = generate_param_grid(params, [])
        assert len(grid) == 6  # 3 * 2
        # Check that all combos exist
        combos = [(g["fast"], g["slow"]) for g in grid]
        assert (5, 20) in combos
        assert (15, 30) in combos

    def test_categorical_param(self):
        cats = [CategoricalParamSpace(name="mode", options=["fast", "slow", "medium"])]
        grid = generate_param_grid([], cats)
        assert len(grid) == 3
        values = [g["mode"] for g in grid]
        assert set(values) == {"fast", "slow", "medium"}

    def test_mixed_numeric_and_categorical(self):
        numeric = [NumericParamSpace(name="period", min=10, max=20, step=10)]
        cats = [CategoricalParamSpace(name="type", options=["SMA", "EMA"])]
        grid = generate_param_grid(numeric, cats)
        assert len(grid) == 4  # 2 * 2

    def test_empty_params(self):
        grid = generate_param_grid([], [])
        assert grid == [{}]

    def test_float_step(self):
        params = [NumericParamSpace(name="multiplier", min=1.0, max=2.0, step=0.5)]
        grid = generate_param_grid(params, [])
        assert len(grid) == 3
        values = [g["multiplier"] for g in grid]
        assert values == [1.0, 1.5, 2.0]

    def test_single_value_range(self):
        params = [NumericParamSpace(name="x", min=5, max=5, step=1)]
        grid = generate_param_grid(params, [])
        assert len(grid) == 1
        assert grid[0]["x"] == 5


class TestSampleRandomParams:
    def test_sample_count(self):
        params = [NumericParamSpace(name="period", min=10, max=50, step=1)]
        samples = sample_random_params(params, [], n_samples=20, seed=42)
        assert len(samples) == 20

    def test_values_within_range(self):
        params = [NumericParamSpace(name="period", min=10, max=50, step=1)]
        samples = sample_random_params(params, [], n_samples=100, seed=42)
        for s in samples:
            assert 10 <= s["period"] <= 50

    def test_seed_reproducibility(self):
        params = [NumericParamSpace(name="period", min=10, max=50, step=1)]
        s1 = sample_random_params(params, [], n_samples=10, seed=123)
        s2 = sample_random_params(params, [], n_samples=10, seed=123)
        assert s1 == s2

    def test_categorical_sampling(self):
        cats = [CategoricalParamSpace(name="mode", options=["a", "b", "c"])]
        samples = sample_random_params([], cats, n_samples=50, seed=42)
        values = {s["mode"] for s in samples}
        # With 50 samples from 3 options, we should see all options
        assert values == {"a", "b", "c"}

    def test_step_alignment(self):
        params = [NumericParamSpace(name="x", min=0, max=10, step=2)]
        samples = sample_random_params(params, [], n_samples=50, seed=42)
        for s in samples:
            assert s["x"] % 2 == 0


class TestRankResults:
    def _make_trial(self, sharpe=0.0, ret=0.0, dd=0.0, **kwargs) -> TrialResult:
        return TrialResult(
            parameters=kwargs.get("params", {}),
            objective_value=0.0,
            sharpe_ratio=sharpe,
            cumulative_return=ret,
            max_drawdown=dd,
            number_of_trades=kwargs.get("trades", 10),
            win_rate=kwargs.get("win_rate", 0.5),
            profit_factor=kwargs.get("pf", 1.0),
            sortino_ratio=kwargs.get("sortino", 0.0),
            strategy_score=kwargs.get("score", 0.0),
        )

    def test_rank_by_sharpe(self):
        trials = [
            self._make_trial(sharpe=0.5),
            self._make_trial(sharpe=2.0),
            self._make_trial(sharpe=1.0),
        ]
        ranked = rank_results(trials, Objective.SHARPE)
        assert ranked[0].sharpe_ratio == 2.0
        assert ranked[1].sharpe_ratio == 1.0
        assert ranked[2].sharpe_ratio == 0.5

    def test_rank_by_return(self):
        trials = [
            self._make_trial(ret=0.1),
            self._make_trial(ret=0.5),
            self._make_trial(ret=0.3),
        ]
        ranked = rank_results(trials, Objective.RETURN)
        assert ranked[0].cumulative_return == 0.5

    def test_rank_by_drawdown(self):
        trials = [
            self._make_trial(dd=0.3),
            self._make_trial(dd=0.1),
            self._make_trial(dd=0.5),
        ]
        ranked = rank_results(trials, Objective.DRAWDOWN)
        # Lower drawdown is better
        assert ranked[0].max_drawdown == 0.1
        assert ranked[1].max_drawdown == 0.3
        assert ranked[2].max_drawdown == 0.5

    def test_empty_results(self):
        ranked = rank_results([], Objective.SHARPE)
        assert ranked == []


class TestGetObjectiveValue:
    def test_sharpe_objective(self):
        trial = TrialResult(
            parameters={},
            objective_value=0.0,
            sharpe_ratio=1.5,
            cumulative_return=0.2,
            max_drawdown=0.1,
            number_of_trades=10,
            win_rate=0.6,
            profit_factor=1.5,
            sortino_ratio=1.0,
            strategy_score=0.5,
        )
        assert get_objective_value(trial, Objective.SHARPE) == 1.5

    def test_return_objective(self):
        trial = TrialResult(
            parameters={},
            objective_value=0.0,
            sharpe_ratio=1.5,
            cumulative_return=0.2,
            max_drawdown=0.1,
            number_of_trades=10,
            win_rate=0.6,
            profit_factor=1.5,
            sortino_ratio=1.0,
            strategy_score=0.5,
        )
        assert get_objective_value(trial, Objective.RETURN) == 0.2

    def test_drawdown_objective_negated(self):
        trial = TrialResult(
            parameters={},
            objective_value=0.0,
            sharpe_ratio=1.5,
            cumulative_return=0.2,
            max_drawdown=0.1,
            number_of_trades=10,
            win_rate=0.6,
            profit_factor=1.5,
            sortino_ratio=1.0,
            strategy_score=0.5,
        )
        assert get_objective_value(trial, Objective.DRAWDOWN) == -0.1
