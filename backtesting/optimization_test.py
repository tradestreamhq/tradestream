import pytest
import numpy as np
from optuna.trial import Trial

from backtesting.optimization import (
    OptimizationConfig,
    StrategyOptimizer,
    ParameterRange,
    PerformanceMetrics
)

class TestStrategyOptimizer:
    @pytest.fixture
    def optimizer(self):
        config = OptimizationConfig(n_trials=10)
        return StrategyOptimizer(config)

    def test_optimize(self, optimizer):
        def objective(trial):
            x = trial.suggest_float('x', -10, 10)
            return -(x**2)  # Simple quadratic function, maximum at x=0
        
        result = optimizer.optimize('test_strategy', objective)
        
        assert 'best_params' in result
        assert 'best_value' in result
        assert 'best_trial' in result
        assert abs(result['best_params']['x']) < 1.0  # Should be close to 0

class TestParameterRange:
    @pytest.fixture
    def trial(self, mocker):
        return mocker.Mock(spec=Trial)

    def test_suggest_ma_periods(self, trial):
        trial.suggest_int.return_value = 50
        period = ParameterRange.suggest_ma_periods(trial, "test_period")
        
        trial.suggest_int.assert_called_once_with("test_period", 5, 200, log=True)
        assert period == 50

    def test_suggest_rsi_period(self, trial):
        trial.suggest_int.return_value = 14
        period = ParameterRange.suggest_rsi_period(trial)
        
        trial.suggest_int.assert_called_once_with("rsi_period", 5, 30)
        assert period == 14

    def test_suggest_threshold(self, trial):
        trial.suggest_float.return_value = 70.0
        threshold = ParameterRange.suggest_threshold(trial, "test_threshold")
        
        trial.suggest_float.assert_called_once_with("test_threshold", 20.0, 80.0)
        assert threshold == 70.0

    def test_suggest_ema_periods(self, trial):
        trial.suggest_int.side_effect = [20, 50]
        short, long = ParameterRange.suggest_ema_periods(trial)
        
        assert short < long
        assert 5 <= short <= 50
        assert short < long <= 200

class TestPerformanceMetrics:
    def test_calculate_sharpe_ratio(self):
        returns = [0.01, -0.005, 0.02, 0.015, -0.01]
        ratio = PerformanceMetrics.calculate_sharpe_ratio(returns)
        assert isinstance(ratio, float)
        assert not np.isnan(ratio)

    def test_calculate_sortino_ratio(self):
        returns = [0.01, -0.005, 0.02, 0.015, -0.01]
        ratio = PerformanceMetrics.calculate_sortino_ratio(returns)
        assert isinstance(ratio, float)
        assert not np.isnan(ratio)

    def test_calculate_max_drawdown(self):
        equity = [100, 95, 97, 90, 95, 100, 98]
        drawdown = PerformanceMetrics.calculate_max_drawdown(equity)
        assert drawdown == 0.10  # Maximum drawdown was 10%

    def test_empty_inputs(self):
        assert PerformanceMetrics.calculate_sharpe_ratio([]) == 0.0
        assert PerformanceMetrics.calculate_sortino_ratio([]) == 0.0
        assert PerformanceMetrics.calculate_max_drawdown([]) == 0.0

if __name__ == '__main__':
    pytest.main([__file__])
