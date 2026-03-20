"""
Monte Carlo Simulation for Strategy Robustness.

Shuffles trade returns to estimate the distribution of outcomes,
providing confidence intervals for key metrics.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd
import vectorbt as vbt

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Result from Monte Carlo simulation."""

    original_result: BacktestMetrics
    median_result: BacktestMetrics
    worst_case_result: BacktestMetrics
    best_case_result: BacktestMetrics
    num_simulations: int
    confidence_level: float
    probability_of_profit: float
    expected_max_drawdown: float
    expected_sharpe: float
    sharpe_std_dev: float
    return_distribution: List[float] = field(default_factory=list)
    drawdown_distribution: List[float] = field(default_factory=list)


class MonteCarloSimulator:
    """Monte Carlo simulator for strategy robustness analysis.

    Reshuffles trade-level PnL to create synthetic equity curves,
    then computes percentile-based confidence intervals.
    """

    def __init__(self, runner: Optional[VectorBTRunner] = None):
        self.runner = runner or VectorBTRunner()

    def run(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        parameters: dict,
        num_simulations: int = 1000,
        confidence_level: float = 0.95,
        random_seed: int = 0,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation by reshuffling trade returns.

        Args:
            ohlcv: OHLCV price data
            strategy_name: Strategy to backtest
            parameters: Strategy parameters
            num_simulations: Number of random reshuffles
            confidence_level: Confidence level for percentile bounds
            random_seed: 0 for random, otherwise reproducible seed
        """
        rng = np.random.default_rng(random_seed if random_seed else None)

        # Run original backtest to get trade-level PnL
        entry_signal, exit_signal = self.runner._generate_signals(
            ohlcv, strategy_name, parameters
        )
        portfolio = vbt.Portfolio.from_signals(
            close=ohlcv["close"],
            entries=entry_signal,
            exits=exit_signal,
            init_cash=10000,
            fees=0.001,
            freq="1min",
        )

        original_result = self.runner.run_strategy(ohlcv, strategy_name, parameters)

        # Extract trade PnLs
        try:
            trades = portfolio.trades.records_readable
            trade_pnls = trades["PnL"].values.copy()
        except Exception:
            trade_pnls = np.array([])

        if len(trade_pnls) < 2:
            # Not enough trades to shuffle — return original as all percentiles
            return MonteCarloResult(
                original_result=original_result,
                median_result=original_result,
                worst_case_result=original_result,
                best_case_result=original_result,
                num_simulations=0,
                confidence_level=confidence_level,
                probability_of_profit=(
                    1.0 if original_result.cumulative_return > 0 else 0.0
                ),
                expected_max_drawdown=original_result.max_drawdown,
                expected_sharpe=original_result.sharpe_ratio,
                sharpe_std_dev=0.0,
                return_distribution=[original_result.cumulative_return],
                drawdown_distribution=[original_result.max_drawdown],
            )

        # Run simulations by reshuffling trade order
        sim_returns = []
        sim_drawdowns = []
        sim_sharpes = []
        init_cash = 10000.0

        for _ in range(num_simulations):
            shuffled_pnls = rng.permutation(trade_pnls)
            equity = self._build_equity_curve(init_cash, shuffled_pnls)
            cum_return = (equity[-1] - init_cash) / init_cash
            max_dd = self._calc_max_drawdown(equity)
            sharpe = self._calc_sharpe_from_pnls(shuffled_pnls, init_cash)

            sim_returns.append(cum_return)
            sim_drawdowns.append(max_dd)
            sim_sharpes.append(sharpe)

        sim_returns = np.array(sim_returns)
        sim_drawdowns = np.array(sim_drawdowns)
        sim_sharpes = np.array(sim_sharpes)

        lower_pct = (1 - confidence_level) * 100
        upper_pct = confidence_level * 100

        median_result = self._metrics_at_percentile(
            sim_returns, sim_drawdowns, sim_sharpes, 50.0
        )
        worst_case_result = self._metrics_at_percentile(
            sim_returns, sim_drawdowns, sim_sharpes, lower_pct
        )
        best_case_result = self._metrics_at_percentile(
            sim_returns, sim_drawdowns, sim_sharpes, upper_pct
        )

        return MonteCarloResult(
            original_result=original_result,
            median_result=median_result,
            worst_case_result=worst_case_result,
            best_case_result=best_case_result,
            num_simulations=num_simulations,
            confidence_level=confidence_level,
            probability_of_profit=float(np.mean(sim_returns > 0)),
            expected_max_drawdown=float(np.percentile(sim_drawdowns, upper_pct)),
            expected_sharpe=float(np.mean(sim_sharpes)),
            sharpe_std_dev=float(np.std(sim_sharpes)),
            return_distribution=sim_returns.tolist(),
            drawdown_distribution=sim_drawdowns.tolist(),
        )

    def _build_equity_curve(self, init_cash: float, pnls: np.ndarray) -> np.ndarray:
        """Build equity curve from sequence of trade PnLs."""
        equity = np.empty(len(pnls) + 1)
        equity[0] = init_cash
        for i, pnl in enumerate(pnls):
            equity[i + 1] = equity[i] + pnl
        return equity

    def _calc_max_drawdown(self, equity: np.ndarray) -> float:
        """Calculate maximum drawdown from equity curve."""
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / np.where(peak > 0, peak, 1.0)
        return float(np.max(drawdown))

    def _calc_sharpe_from_pnls(self, pnls: np.ndarray, init_cash: float) -> float:
        """Approximate Sharpe ratio from trade PnLs."""
        if len(pnls) == 0 or np.std(pnls) == 0:
            return 0.0
        # Normalize PnLs as returns relative to initial cash
        returns = pnls / init_cash
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))

    def _metrics_at_percentile(
        self,
        sim_returns: np.ndarray,
        sim_drawdowns: np.ndarray,
        sim_sharpes: np.ndarray,
        percentile: float,
    ) -> BacktestMetrics:
        """Create BacktestMetrics at a given percentile of simulation results."""
        return BacktestMetrics(
            cumulative_return=float(np.percentile(sim_returns, percentile)),
            annualized_return=0.0,
            sharpe_ratio=float(np.percentile(sim_sharpes, percentile)),
            sortino_ratio=0.0,
            max_drawdown=float(np.percentile(sim_drawdowns, percentile)),
            volatility=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            number_of_trades=0,
            average_trade_duration=0.0,
            alpha=0.0,
            beta=1.0,
            strategy_score=0.0,
        )
