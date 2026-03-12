"""
Performance metrics for backtesting results.

Calculates key trading metrics: Sharpe ratio, max drawdown, win rate,
profit factor, and total return from a series of trades.
"""

from dataclasses import dataclass, field
from typing import List

import math


@dataclass
class Trade:
    """A single completed trade."""

    entry_price: float
    exit_price: float
    entry_index: int
    exit_index: int
    symbol: str
    direction: str = "long"  # "long" or "short"

    @property
    def pnl(self) -> float:
        if self.direction == "long":
            return self.exit_price - self.entry_price
        return self.entry_price - self.exit_price

    @property
    def return_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return self.pnl / self.entry_price

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def duration(self) -> int:
        return self.exit_index - self.entry_index


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics from a backtest run."""

    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade_duration: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    symbols: List[str] = field(default_factory=list)


def calculate_metrics(
    trades: List[Trade],
    risk_free_rate: float = 0.02,
    periods_per_year: float = 252.0,
) -> PerformanceMetrics:
    """
    Calculate performance metrics from a list of completed trades.

    Args:
        trades: List of completed Trade objects.
        risk_free_rate: Annual risk-free rate for Sharpe calculation.
        periods_per_year: Number of trading periods per year (252 for daily).

    Returns:
        PerformanceMetrics with all calculated values.
    """
    if not trades:
        return PerformanceMetrics()

    returns = [t.return_pct for t in trades]
    winners = [t for t in trades if t.is_winner]
    losers = [t for t in trades if not t.is_winner]
    symbols = list(set(t.symbol for t in trades))

    total_return = _total_return(returns)
    sharpe = _sharpe_ratio(returns, risk_free_rate, periods_per_year)
    max_dd = _max_drawdown(returns)
    win_rate = len(winners) / len(trades) if trades else 0.0
    pf = _profit_factor(trades)

    avg_win = (
        sum(t.return_pct for t in winners) / len(winners) if winners else 0.0
    )
    avg_loss = (
        sum(t.return_pct for t in losers) / len(losers) if losers else 0.0
    )
    avg_duration = sum(t.duration for t in trades) / len(trades)

    max_consec_wins, max_consec_losses = _max_consecutive(trades)

    return PerformanceMetrics(
        total_return=total_return,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        profit_factor=pf,
        total_trades=len(trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        avg_win=avg_win,
        avg_loss=avg_loss,
        avg_trade_duration=avg_duration,
        max_consecutive_wins=max_consec_wins,
        max_consecutive_losses=max_consec_losses,
        symbols=symbols,
    )


def _total_return(returns: List[float]) -> float:
    """Calculate compounded total return from trade returns."""
    if not returns:
        return 0.0
    cumulative = 1.0
    for r in returns:
        cumulative *= 1 + r
    return cumulative - 1


def _sharpe_ratio(
    returns: List[float],
    risk_free_rate: float,
    periods_per_year: float,
) -> float:
    """
    Calculate annualized Sharpe ratio.

    Sharpe = (mean_return - rf_per_period) / std(returns) * sqrt(periods_per_year)
    """
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    rf_per_period = risk_free_rate / periods_per_year
    excess_mean = mean_return - rf_per_period

    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return 0.0

    return (excess_mean / std_dev) * math.sqrt(periods_per_year)


def _max_drawdown(returns: List[float]) -> float:
    """
    Calculate maximum drawdown from peak equity.

    Returns a positive value (e.g., 0.15 means 15% drawdown).
    """
    if not returns:
        return 0.0

    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        equity *= 1 + r
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    return max_dd


def _profit_factor(trades: List[Trade]) -> float:
    """
    Calculate profit factor = gross_profit / gross_loss.

    Returns inf if no losing trades, 0.0 if no winning trades.
    """
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _max_consecutive(trades: List[Trade]) -> tuple:
    """Calculate max consecutive wins and losses."""
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for t in trades:
        if t.is_winner:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)

    return max_wins, max_losses
