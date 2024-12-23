from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import optuna
from optuna.trial import Trial
import numpy as np

@dataclass
class OptimizationConfig:
    n_trials: int = 100
    timeout: Optional[int] = None
    n_jobs: int = 1

class StrategyOptimizer:
    """Handles optimization of strategy parameters using Optuna."""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        
    def optimize(self, strategy_type: str, objective_fn) -> Dict[str, Any]:
        """Run optimization for the given strategy type and objective function."""
        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(n_startup_trials=10)
        )
        
        study.optimize(
            objective_fn,
            n_trials=self.config.n_trials,
            timeout=self.config.timeout,
            n_jobs=self.config.n_jobs
        )
        
        return {
            'best_params': study.best_params,
            'best_value': study.best_value,
            'best_trial': study.best_trial,
            'trials_dataframe': study.trials_dataframe()
        }

class ParameterRange:
    """Defines parameter ranges and sampling methods for optimization."""
    
    @staticmethod
    def suggest_ma_periods(trial: Trial, name: str, min_period: int = 5, max_period: int = 200) -> int:
        return trial.suggest_int(name, min_period, max_period, log=True)
    
    @staticmethod
    def suggest_rsi_period(trial: Trial, name: str = "rsi_period") -> int:
        return trial.suggest_int(name, 5, 30)
        
    @staticmethod
    def suggest_threshold(trial: Trial, name: str, low: float = 20.0, high: float = 80.0) -> float:
        return trial.suggest_float(name, low, high)

    @staticmethod
    def suggest_ema_periods(trial: Trial) -> tuple[int, int]:
        """Suggests EMA periods ensuring short < long."""
        short = trial.suggest_int("short_period", 5, 50, log=True)
        long = trial.suggest_int("long_period", short + 1, 200, log=True)
        return short, long
        
    @staticmethod
    def suggest_momentum_params(trial: Trial) -> Dict[str, Any]:
        return {
            "momentum_period": trial.suggest_int("momentum_period", 5, 50, log=True),
            "sma_period": trial.suggest_int("sma_period", 5, 100, log=True)
        }

class PerformanceMetrics:
    """Calculates various performance metrics for strategy evaluation."""
    
    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        returns = np.array(returns)
        excess_returns = returns - risk_free_rate
        if len(excess_returns) < 2:
            return 0.0
        return np.mean(excess_returns) / np.std(excess_returns, ddof=1) * np.sqrt(252)
    
    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        returns = np.array(returns)
        excess_returns = returns - risk_free_rate
        downside_returns = np.where(returns < 0, returns, 0)
        if len(downside_returns) < 2:
            return 0.0
        return np.mean(excess_returns) / np.std(downside_returns, ddof=1) * np.sqrt(252)
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: List[float]) -> float:
        peaks = np.maximum.accumulate(equity_curve)
        drawdowns = (peaks - equity_curve) / peaks
        return np.max(drawdowns) if len(drawdowns) > 0 else 0.0
