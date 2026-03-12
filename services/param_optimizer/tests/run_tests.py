#!/usr/bin/env python3
"""Test runner that stubs heavy dependencies before importing test modules."""

import os
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, project_root)


# --- Stub heavy dependencies BEFORE any package imports ---
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


for mod_name in ("numpy", "np", "pandas", "pd", "vectorbt", "vbt", "numba"):
    sys.modules.setdefault(mod_name, MagicMock())

_runner_stub = type(sys)("services.backtesting.vectorbt_runner")
_runner_stub.BacktestMetrics = _BacktestMetrics
_runner_stub.VectorBTRunner = MagicMock

_registry_stub = type(sys)("services.backtesting.indicator_registry")
_registry_stub.IndicatorRegistry = MagicMock
_registry_stub.get_default_registry = MagicMock

sys.modules["services.backtesting.vectorbt_runner"] = _runner_stub
sys.modules["services.backtesting.indicator_registry"] = _registry_stub
# --- End stubs ---

import unittest  # noqa: E402

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern="test_*.py",
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
