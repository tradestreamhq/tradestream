"""
Backtesting engine — runs strategy signals against historical OHLCV data.

Produces simulated trades and calculates performance metrics:
total return, Sharpe ratio, max drawdown, win rate, profit factor.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    side: str  # "BUY" or "SELL"
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: float = 1.0
    pnl: Optional[float] = None


@dataclass
class EquityPoint:
    timestamp: datetime
    equity: float
    drawdown: float


@dataclass
class BacktestResult:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[EquityPoint] = field(default_factory=list)


def generate_signals(candles: List[Candle], strategy_id: str) -> List[int]:
    """Generate trading signals from candles using a simple SMA crossover.

    Returns a list of signals: 1 = buy, -1 = sell, 0 = hold.
    The strategy_id selects the strategy parameters.
    """
    if len(candles) < 2:
        return [0] * len(candles)

    # Use SMA crossover with configurable periods based on strategy_id hash
    hash_val = sum(ord(c) for c in strategy_id)
    short_period = max(5, (hash_val % 10) + 5)
    long_period = max(short_period + 5, (hash_val % 20) + 15)

    closes = [c.close for c in candles]
    signals = [0] * len(candles)

    for i in range(long_period, len(candles)):
        short_sma = sum(closes[i - short_period : i]) / short_period
        long_sma = sum(closes[i - long_period : i]) / long_period

        prev_short = sum(closes[i - short_period - 1 : i - 1]) / short_period
        prev_long = sum(closes[i - long_period - 1 : i - 1]) / long_period

        # Crossover detection
        if short_sma > long_sma and prev_short <= prev_long:
            signals[i] = 1  # Buy signal
        elif short_sma < long_sma and prev_short >= prev_long:
            signals[i] = -1  # Sell signal

    return signals


def run_backtest(
    candles: List[Candle],
    strategy_id: str,
    initial_capital: float = 10000.0,
) -> BacktestResult:
    """Execute a backtest of a strategy against historical OHLCV data.

    Simulates trading by generating signals and tracking positions/equity.
    """
    if not candles:
        return BacktestResult(
            total_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
        )

    signals = generate_signals(candles, strategy_id)

    trades: List[Trade] = []
    equity_curve: List[EquityPoint] = []
    capital = initial_capital
    position: Optional[Trade] = None
    peak_equity = initial_capital
    max_dd = 0.0
    returns: List[float] = []
    prev_equity = initial_capital

    for i, candle in enumerate(candles):
        signal = signals[i]

        # Close position on sell signal
        if signal == -1 and position is not None:
            position.exit_time = candle.timestamp
            position.exit_price = candle.close
            position.pnl = (candle.close - position.entry_price) * position.quantity
            capital += position.pnl
            trades.append(position)
            position = None

        # Open position on buy signal
        elif signal == 1 and position is None:
            qty = capital / candle.close  # invest full capital
            position = Trade(
                side="BUY",
                entry_time=candle.timestamp,
                entry_price=candle.close,
                quantity=qty,
            )

        # Track equity
        current_equity = capital
        if position is not None:
            unrealized = (candle.close - position.entry_price) * position.quantity
            current_equity = capital + unrealized

        peak_equity = max(peak_equity, current_equity)
        dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
        max_dd = max(max_dd, dd)

        equity_curve.append(
            EquityPoint(
                timestamp=candle.timestamp,
                equity=current_equity,
                drawdown=dd,
            )
        )

        # Track period return for Sharpe calculation
        if prev_equity > 0:
            period_return = (current_equity - prev_equity) / prev_equity
            returns.append(period_return)
        prev_equity = current_equity

    # Close any remaining open position at last candle
    if position is not None and candles:
        last = candles[-1]
        position.exit_time = last.timestamp
        position.exit_price = last.close
        position.pnl = (last.close - position.entry_price) * position.quantity
        capital += position.pnl
        trades.append(position)

    # Calculate metrics
    final_equity = capital
    total_return = (final_equity - initial_capital) / initial_capital

    # Sharpe ratio (annualized, assuming daily candles ~252 trading days)
    sharpe = 0.0
    if len(returns) > 1:
        avg_ret = sum(returns) / len(returns)
        std_ret = math.sqrt(
            sum((r - avg_ret) ** 2 for r in returns) / (len(returns) - 1)
        )
        if std_ret > 0:
            sharpe = (avg_ret / std_ret) * math.sqrt(252)

    # Win rate
    closed_trades = [t for t in trades if t.pnl is not None]
    winning = [t for t in closed_trades if t.pnl > 0]
    win_rate = len(winning) / len(closed_trades) if closed_trades else 0.0

    # Profit factor
    gross_profit = sum(t.pnl for t in closed_trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in closed_trades if t.pnl <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    if math.isinf(profit_factor):
        profit_factor = 0.0 if gross_profit == 0 else 999.99

    return BacktestResult(
        total_return=round(total_return, 6),
        sharpe_ratio=round(sharpe, 4),
        max_drawdown=round(max_dd, 6),
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4),
        total_trades=len(closed_trades),
        trades=trades,
        equity_curve=equity_curve,
    )
