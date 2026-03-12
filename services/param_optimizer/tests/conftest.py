"""Test configuration: stub out heavy dependencies before any imports."""

import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock


@dataclass
class _BacktestMetrics:
    cumulative_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    number_of_trades: int = 0
    average_trade_duration: float = 0.0
    alpha: float = 0.0
    beta: float = 1.0
    strategy_score: float = 0.0


# Stub heavy deps that aren't installed in CI/test env
for mod_name in ("numpy", "pandas", "vectorbt", "numba", "vbt"):
    sys.modules.setdefault(mod_name, MagicMock())

# Provide a stub vectorbt_runner module with a real BacktestMetrics dataclass
_runner_stub = type(sys)("services.backtesting.vectorbt_runner")
_runner_stub.BacktestMetrics = _BacktestMetrics
_runner_stub.VectorBTRunner = MagicMock

# Also stub indicator_registry
_registry_stub = type(sys)("services.backtesting.indicator_registry")
_registry_stub.IndicatorRegistry = MagicMock
_registry_stub.get_default_registry = MagicMock

sys.modules["services.backtesting.vectorbt_runner"] = _runner_stub
sys.modules["services.backtesting.indicator_registry"] = _registry_stub
