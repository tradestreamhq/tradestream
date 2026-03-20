"""
Portfolio-Level Backtesting.

Runs multiple strategies simultaneously with capital allocation weights,
computes aggregate portfolio metrics and inter-strategy correlations.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import vectorbt as vbt

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner

logger = logging.getLogger(__name__)


@dataclass
class StrategyAllocation:
    """A strategy with its capital weight."""

    strategy_name: str
    parameters: dict
    weight: float  # 0.0 to 1.0


@dataclass
class StrategyResult:
    """Per-strategy result within a portfolio."""

    strategy_name: str
    weight: float
    result: BacktestMetrics
    return_contribution: float
    risk_contribution: float


@dataclass
class PortfolioBacktestResult:
    """Result from portfolio-level backtesting."""

    portfolio_result: BacktestMetrics
    strategy_results: List[StrategyResult]
    correlation_matrix: List[float]  # flattened row-major
    num_strategies: int
    diversification_ratio: float


class PortfolioBacktester:
    """Portfolio-level backtester running multiple strategies with capital allocation."""

    def __init__(self, runner: Optional[VectorBTRunner] = None):
        self.runner = runner or VectorBTRunner()

    def run(
        self,
        ohlcv: pd.DataFrame,
        allocations: List[StrategyAllocation],
        initial_capital: float = 10000.0,
        rebalance_frequency_bars: int = 0,
    ) -> PortfolioBacktestResult:
        """Run portfolio-level backtest.

        Args:
            ohlcv: OHLCV price data
            allocations: List of strategy allocations with weights
            initial_capital: Starting capital
            rebalance_frequency_bars: Bars between rebalances (0 = no rebalancing)
        """
        if not allocations:
            raise ValueError("At least one strategy allocation is required")

        weight_sum = sum(a.weight for a in allocations)
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(
                f"Allocation weights must sum to 1.0, got {weight_sum:.4f}"
            )

        # Run each strategy and collect returns
        strategy_returns = {}
        strategy_metrics = {}

        for alloc in allocations:
            entry_signal, exit_signal = self.runner._generate_signals(
                ohlcv, alloc.strategy_name, alloc.parameters
            )
            portfolio = vbt.Portfolio.from_signals(
                close=ohlcv["close"],
                entries=entry_signal,
                exits=exit_signal,
                init_cash=initial_capital * alloc.weight,
                fees=0.001,
                freq="1min",
            )
            returns = portfolio.returns()
            strategy_returns[alloc.strategy_name] = returns
            strategy_metrics[alloc.strategy_name] = self.runner.run_strategy(
                ohlcv, alloc.strategy_name, alloc.parameters
            )

        # Build weighted portfolio returns
        weights = {a.strategy_name: a.weight for a in allocations}
        portfolio_returns = pd.Series(0.0, index=ohlcv.index)
        for name, returns in strategy_returns.items():
            portfolio_returns += weights[name] * returns

        # Compute portfolio-level metrics
        portfolio_metrics = self._compute_portfolio_metrics(
            portfolio_returns, initial_capital, len(ohlcv)
        )

        # Build per-strategy results
        strat_results = []
        for alloc in allocations:
            metrics = strategy_metrics[alloc.strategy_name]
            return_contribution = alloc.weight * metrics.cumulative_return
            risk_contribution = alloc.weight * metrics.volatility
            strat_results.append(
                StrategyResult(
                    strategy_name=alloc.strategy_name,
                    weight=alloc.weight,
                    result=metrics,
                    return_contribution=return_contribution,
                    risk_contribution=risk_contribution,
                )
            )

        # Correlation matrix
        returns_df = pd.DataFrame(strategy_returns)
        corr_matrix = returns_df.corr().values
        # Replace NaN with 0 (can happen with zero-variance returns)
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)
        flat_corr = corr_matrix.flatten().tolist()

        # Diversification ratio
        div_ratio = self._calc_diversification_ratio(
            allocations, strategy_returns, corr_matrix
        )

        return PortfolioBacktestResult(
            portfolio_result=portfolio_metrics,
            strategy_results=strat_results,
            correlation_matrix=flat_corr,
            num_strategies=len(allocations),
            diversification_ratio=div_ratio,
        )

    def _compute_portfolio_metrics(
        self,
        portfolio_returns: pd.Series,
        initial_capital: float,
        num_bars: int,
    ) -> BacktestMetrics:
        """Compute aggregate portfolio metrics from weighted returns."""
        bars_per_year = 252 * 1440
        risk_free_rate = 0.02

        cum_return = float((1 + portfolio_returns).prod() - 1)
        years = num_bars / bars_per_year
        ann_return = float((1 + cum_return) ** (1 / max(years, 1e-9)) - 1)

        vol = float(portfolio_returns.std()) if len(portfolio_returns) > 1 else 0.0

        # Sharpe
        if vol > 0:
            excess = portfolio_returns.mean() - risk_free_rate / bars_per_year
            sharpe = float(excess / vol * np.sqrt(bars_per_year))
        else:
            sharpe = 0.0

        # Sortino
        neg_returns = portfolio_returns[portfolio_returns < 0]
        if len(neg_returns) > 0 and neg_returns.std() > 0:
            excess = portfolio_returns.mean() - risk_free_rate / bars_per_year
            sortino = float(excess / neg_returns.std() * np.sqrt(bars_per_year))
        else:
            sortino = 0.0

        # Max drawdown
        equity = (1 + portfolio_returns).cumprod()
        peak = equity.cummax()
        drawdown = (peak - equity) / peak.replace(0, 1)
        max_dd = float(drawdown.max()) if len(drawdown) > 0 else 0.0

        return BacktestMetrics(
            cumulative_return=cum_return,
            annualized_return=ann_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            volatility=vol,
            win_rate=0.0,
            profit_factor=0.0,
            number_of_trades=0,
            average_trade_duration=0.0,
            alpha=0.0,
            beta=1.0,
            strategy_score=0.0,
        )

    def _calc_diversification_ratio(
        self,
        allocations: List[StrategyAllocation],
        strategy_returns: Dict[str, pd.Series],
        corr_matrix: np.ndarray,
    ) -> float:
        """Calculate portfolio diversification ratio.

        DR = weighted sum of individual volatilities / portfolio volatility.
        DR > 1 means the portfolio benefits from diversification.
        """
        weights = np.array([a.weight for a in allocations])
        vols = np.array([strategy_returns[a.strategy_name].std() for a in allocations])

        weighted_vol_sum = float(np.dot(weights, vols))

        # Portfolio variance = w' * Sigma * w
        cov_matrix = np.outer(vols, vols) * corr_matrix
        port_variance = float(weights @ cov_matrix @ weights)
        port_vol = np.sqrt(max(port_variance, 0))

        if port_vol > 1e-12:
            return weighted_vol_sum / port_vol
        return 1.0
