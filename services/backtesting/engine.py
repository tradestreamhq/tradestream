"""
Backtesting engine that replays historical market data through a strategy.

Tracks positions, trades, and P&L throughout the simulation, and generates
summary statistics including total return, Sharpe ratio, max drawdown,
number of trades, and average holding period.
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class CommissionModel:
    """Configurable commission model for backtesting."""

    flat_fee: float = 0.0
    percentage: float = 0.001  # 0.1% default
    min_commission: float = 0.0

    def calculate(self, trade_value: float) -> float:
        commission = self.flat_fee + abs(trade_value) * self.percentage
        return max(commission, self.min_commission)


@dataclass
class Trade:
    """A completed round-trip trade."""

    trade_id: str
    direction: TradeDirection
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    pnl: float
    commission: float
    holding_period_bars: int


@dataclass
class Position:
    """An open position being tracked during the backtest."""

    direction: TradeDirection
    entry_time: datetime
    entry_price: float
    quantity: float
    entry_index: int


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 10000.0
    commission: Optional[CommissionModel] = None
    position_size_pct: float = 1.0  # fraction of capital per trade

    def __post_init__(self):
        if self.commission is None:
            self.commission = CommissionModel()


@dataclass
class BacktestSummary:
    """Summary statistics from a completed backtest."""

    backtest_id: str
    strategy_name: str
    config: Dict[str, Any]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration_bars: int
    number_of_trades: int
    win_rate: float
    profit_factor: float
    avg_holding_period_bars: float
    avg_win: float
    avg_loss: float
    total_commission: float
    equity_curve: List[float]
    trades: List[Dict[str, Any]]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BacktestEngine:
    """
    Core backtesting engine that replays market data through a strategy.

    Supports configurable date ranges, initial capital, and commission models.
    Tracks simulated positions, trades, and P&L throughout the simulation.
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        ohlcv: pd.DataFrame,
        entry_signals: pd.Series,
        exit_signals: pd.Series,
        strategy_name: str = "unnamed",
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> BacktestSummary:
        """
        Run a backtest with entry/exit signals on OHLCV data.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume]
                   and a DatetimeIndex.
            entry_signals: Boolean series aligned with ohlcv index.
            exit_signals: Boolean series aligned with ohlcv index.
            strategy_name: Name of the strategy for labeling results.
            strategy_params: Parameters used by the strategy.

        Returns:
            BacktestSummary with full results and statistics.
        """
        data = self._filter_date_range(ohlcv)
        entries = entry_signals.reindex(data.index, fill_value=False)
        exits = exit_signals.reindex(data.index, fill_value=False)

        capital = self.config.initial_capital
        position: Optional[Position] = None
        trades: List[Trade] = []
        equity_curve: List[float] = []
        total_commission = 0.0

        for i, (timestamp, row) in enumerate(data.iterrows()):
            price = row["close"]

            # Check exit first
            if position is not None and exits.iloc[i]:
                trade_value = position.quantity * price
                exit_commission = self.config.commission.calculate(trade_value)
                total_commission += exit_commission

                if position.direction == TradeDirection.LONG:
                    pnl = (price - position.entry_price) * position.quantity
                else:
                    pnl = (position.entry_price - price) * position.quantity

                pnl -= exit_commission

                trades.append(
                    Trade(
                        trade_id=str(uuid.uuid4()),
                        direction=position.direction,
                        entry_time=position.entry_time,
                        entry_price=position.entry_price,
                        exit_time=timestamp,
                        exit_price=price,
                        quantity=position.quantity,
                        pnl=pnl,
                        commission=exit_commission,
                        holding_period_bars=i - position.entry_index,
                    )
                )

                capital += pnl
                position = None

            # Check entry
            if position is None and entries.iloc[i]:
                trade_capital = capital * self.config.position_size_pct
                entry_commission = self.config.commission.calculate(trade_capital)
                total_commission += entry_commission
                trade_capital -= entry_commission
                quantity = trade_capital / price if price > 0 else 0

                if quantity > 0:
                    position = Position(
                        direction=TradeDirection.LONG,
                        entry_time=timestamp,
                        entry_price=price,
                        quantity=quantity,
                        entry_index=i,
                    )

            # Mark-to-market for equity curve
            if position is not None:
                unrealized = (price - position.entry_price) * position.quantity
                equity_curve.append(capital + unrealized)
            else:
                equity_curve.append(capital)

        # Close any remaining open position at last price
        if position is not None and len(data) > 0:
            last_price = data["close"].iloc[-1]
            last_time = data.index[-1]
            trade_value = position.quantity * last_price
            exit_commission = self.config.commission.calculate(trade_value)
            total_commission += exit_commission
            pnl = (last_price - position.entry_price) * position.quantity
            pnl -= exit_commission

            trades.append(
                Trade(
                    trade_id=str(uuid.uuid4()),
                    direction=position.direction,
                    entry_time=position.entry_time,
                    entry_price=position.entry_price,
                    exit_time=last_time,
                    exit_price=last_price,
                    quantity=position.quantity,
                    pnl=pnl,
                    commission=exit_commission,
                    holding_period_bars=len(data) - 1 - position.entry_index,
                )
            )
            capital += pnl

        final_capital = capital
        equity = np.array(equity_curve) if equity_curve else np.array([capital])

        summary = self._compute_summary(
            backtest_id=str(uuid.uuid4()),
            strategy_name=strategy_name,
            strategy_params=strategy_params or {},
            data=data,
            trades=trades,
            equity=equity,
            initial_capital=self.config.initial_capital,
            final_capital=final_capital,
            total_commission=total_commission,
        )

        return summary

    def _filter_date_range(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        data = ohlcv.copy()
        if self.config.start_date:
            data = data[data.index >= pd.Timestamp(self.config.start_date)]
        if self.config.end_date:
            data = data[data.index <= pd.Timestamp(self.config.end_date)]
        return data

    def _compute_summary(
        self,
        backtest_id: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        data: pd.DataFrame,
        trades: List[Trade],
        equity: np.ndarray,
        initial_capital: float,
        final_capital: float,
        total_commission: float,
    ) -> BacktestSummary:
        total_return = (
            (final_capital - initial_capital) / initial_capital
            if initial_capital > 0
            else 0.0
        )

        # Returns series from equity curve
        if len(equity) > 1:
            returns = np.diff(equity) / equity[:-1]
        else:
            returns = np.array([0.0])

        num_bars = len(data)
        bars_per_year = 252 * 390  # assuming minute bars, 6.5hr trading day
        years = num_bars / bars_per_year if bars_per_year > 0 else 1.0

        annualized_return = (
            ((1 + total_return) ** (1 / years) - 1) if years > 0 else 0.0
        )

        sharpe = self._calc_sharpe(returns, bars_per_year)
        sortino = self._calc_sortino(returns, bars_per_year)
        max_dd, max_dd_duration = self._calc_max_drawdown(equity)

        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        win_rate = len(winning) / len(trades) if trades else 0.0
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0
            else (float("inf") if gross_profit > 0 else 0.0)
        )

        avg_holding = (
            np.mean([t.holding_period_bars for t in trades]) if trades else 0.0
        )
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0.0
        avg_loss = np.mean([t.pnl for t in losing]) if losing else 0.0

        start_date = str(data.index[0]) if len(data) > 0 else ""
        end_date = str(data.index[-1]) if len(data) > 0 else ""

        trade_dicts = [
            {
                "trade_id": t.trade_id,
                "direction": t.direction.value,
                "entry_time": str(t.entry_time),
                "entry_price": t.entry_price,
                "exit_time": str(t.exit_time),
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "commission": t.commission,
                "holding_period_bars": t.holding_period_bars,
            }
            for t in trades
        ]

        return BacktestSummary(
            backtest_id=backtest_id,
            strategy_name=strategy_name,
            config={
                "initial_capital": self.config.initial_capital,
                "commission_pct": self.config.commission.percentage,
                "commission_flat": self.config.commission.flat_fee,
                "position_size_pct": self.config.position_size_pct,
                **strategy_params,
            },
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_duration_bars=max_dd_duration,
            number_of_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_holding_period_bars=float(avg_holding),
            avg_win=float(avg_win),
            avg_loss=float(avg_loss),
            total_commission=total_commission,
            equity_curve=equity.tolist(),
            trades=trade_dicts,
            created_at=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def _calc_sharpe(
        returns: np.ndarray, bars_per_year: int, risk_free_rate: float = 0.02
    ) -> float:
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        excess = np.mean(returns) - risk_free_rate / bars_per_year
        return float(excess / np.std(returns) * np.sqrt(bars_per_year))

    @staticmethod
    def _calc_sortino(
        returns: np.ndarray, bars_per_year: int, risk_free_rate: float = 0.02
    ) -> float:
        if len(returns) < 2:
            return 0.0
        downside = returns[returns < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        excess = np.mean(returns) - risk_free_rate / bars_per_year
        return float(excess / np.std(downside) * np.sqrt(bars_per_year))

    @staticmethod
    def _calc_max_drawdown(equity: np.ndarray) -> Tuple[float, int]:
        if len(equity) < 2:
            return 0.0, 0

        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak

        max_dd = float(np.max(drawdown))

        # Calculate max drawdown duration
        max_duration = 0
        current_duration = 0
        for dd in drawdown:
            if dd > 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_dd, max_duration
