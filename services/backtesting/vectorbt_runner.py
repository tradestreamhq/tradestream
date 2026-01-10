"""
VectorBT Backtesting Runner.

Implements the core backtesting logic using VectorBT for vectorized operations.
"""

import numpy as np
import pandas as pd
import vectorbt as vbt
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

from indicator_registry import get_default_registry, IndicatorRegistry


@dataclass
class BacktestMetrics:
    """Results from a backtest run."""

    cumulative_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    volatility: float
    win_rate: float
    profit_factor: float
    number_of_trades: int
    average_trade_duration: float
    alpha: float
    beta: float
    strategy_score: float


class VectorBTRunner:
    """Backtesting runner using VectorBT for vectorized operations."""

    def __init__(self, indicator_registry: Optional[IndicatorRegistry] = None):
        self.registry = indicator_registry or get_default_registry()
        self._risk_free_rate = 0.02  # 2% annual risk-free rate
        self._bars_per_year = 252 * 1440  # 1-minute bars, 252 trading days

    def run_backtest(
        self,
        ohlcv: pd.DataFrame,
        entry_signal: pd.Series,
        exit_signal: pd.Series,
    ) -> BacktestMetrics:
        """
        Run a backtest with given entry/exit signals.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume]
            entry_signal: Boolean series for entry signals
            exit_signal: Boolean series for exit signals

        Returns:
            BacktestMetrics with performance results
        """
        # Build portfolio using VectorBT
        portfolio = vbt.Portfolio.from_signals(
            close=ohlcv["close"],
            entries=entry_signal,
            exits=exit_signal,
            init_cash=10000,
            fees=0.001,  # 0.1% trading fee
            freq="1min",
        )

        # Extract metrics
        returns = portfolio.returns()

        return BacktestMetrics(
            cumulative_return=self._calc_cumulative_return(portfolio),
            annualized_return=self._calc_annualized_return(portfolio, len(ohlcv)),
            sharpe_ratio=self._calc_sharpe_ratio(returns),
            sortino_ratio=self._calc_sortino_ratio(returns),
            max_drawdown=self._calc_max_drawdown(portfolio),
            volatility=self._calc_volatility(returns),
            win_rate=self._calc_win_rate(portfolio),
            profit_factor=self._calc_profit_factor(portfolio),
            number_of_trades=self._calc_num_trades(portfolio),
            average_trade_duration=self._calc_avg_trade_duration(portfolio),
            alpha=0.0,  # Placeholder - requires benchmark
            beta=1.0,  # Placeholder - requires benchmark
            strategy_score=0.0,  # Calculated after other metrics
        )

    def run_strategy(
        self, ohlcv: pd.DataFrame, strategy_name: str, parameters: Dict[str, Any]
    ) -> BacktestMetrics:
        """
        Run a named strategy with given parameters.

        Args:
            ohlcv: OHLCV DataFrame
            strategy_name: Name of the strategy (e.g., "SMA_RSI", "MACD_CROSSOVER")
            parameters: Strategy-specific parameters

        Returns:
            BacktestMetrics with performance results
        """
        # Generate entry/exit signals based on strategy
        entry_signal, exit_signal = self._generate_signals(
            ohlcv, strategy_name, parameters
        )

        # Run backtest
        metrics = self.run_backtest(ohlcv, entry_signal, exit_signal)

        # Calculate strategy score
        metrics = self._with_strategy_score(metrics)

        return metrics

    def run_batch(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        parameter_sets: List[Dict[str, Any]],
    ) -> List[BacktestMetrics]:
        """
        Run multiple backtests with different parameter sets (vectorized).

        This is optimized for GA optimization where we need to evaluate
        many parameter combinations efficiently.
        """
        results = []

        # For true vectorization, we'd need to restructure the signals
        # For now, use loop but leverage VectorBT's efficiency
        for params in parameter_sets:
            metrics = self.run_strategy(ohlcv, strategy_name, params)
            results.append(metrics)

        return results

    def _generate_signals(
        self, ohlcv: pd.DataFrame, strategy_name: str, parameters: Dict[str, Any]
    ) -> Tuple[pd.Series, pd.Series]:
        """Generate entry/exit signals for a strategy."""
        # Initialize signals
        entries = pd.Series(False, index=ohlcv.index)
        exits = pd.Series(False, index=ohlcv.index)

        # Strategy implementations
        if strategy_name == "SMA_RSI":
            entries, exits = self._sma_rsi_signals(ohlcv, parameters)
        elif strategy_name == "MACD_CROSSOVER":
            entries, exits = self._macd_crossover_signals(ohlcv, parameters)
        elif strategy_name == "EMA_MACD":
            entries, exits = self._ema_macd_signals(ohlcv, parameters)
        elif strategy_name == "SMA_EMA_CROSSOVER":
            entries, exits = self._sma_ema_crossover_signals(ohlcv, parameters)
        elif strategy_name == "RSI_EMA_CROSSOVER":
            entries, exits = self._rsi_ema_crossover_signals(ohlcv, parameters)
        elif strategy_name == "BOLLINGER_BANDS":
            entries, exits = self._bbands_signals(ohlcv, parameters)
        elif strategy_name == "ADX_STOCHASTIC":
            entries, exits = self._adx_stochastic_signals(ohlcv, parameters)
        elif strategy_name == "DOUBLE_EMA_CROSSOVER":
            entries, exits = self._double_ema_crossover_signals(ohlcv, parameters)
        elif strategy_name == "TRIPLE_EMA_CROSSOVER":
            entries, exits = self._triple_ema_crossover_signals(ohlcv, parameters)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        return entries, exits

    # Strategy signal generators
    def _sma_rsi_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """SMA + RSI strategy signals."""
        close = ohlcv["close"]
        ma_period = params.get("movingAveragePeriod", 20)
        rsi_period = params.get("rsiPeriod", 14)
        oversold = params.get("oversoldThreshold", 30)
        overbought = params.get("overboughtThreshold", 70)

        sma = self.registry.create("SMA", close, ohlcv, {"period": ma_period})
        rsi = self.registry.create("RSI", close, ohlcv, {"period": rsi_period})

        # Entry: price > SMA and RSI crosses above oversold
        price_above_sma = close > sma
        rsi_oversold_cross = (rsi.shift(1) <= oversold) & (rsi > oversold)
        entries = price_above_sma & rsi_oversold_cross

        # Exit: price < SMA or RSI crosses below overbought
        price_below_sma = close < sma
        rsi_overbought_cross = (rsi.shift(1) >= overbought) & (rsi < overbought)
        exits = price_below_sma | rsi_overbought_cross

        return entries, exits

    def _macd_crossover_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """MACD crossover strategy signals."""
        close = ohlcv["close"]
        fast = params.get("shortEmaPeriod", 12)
        slow = params.get("longEmaPeriod", 26)
        signal_period = params.get("signalPeriod", 9)

        macd = vbt.MACD.run(
            close, fast_window=fast, slow_window=slow, signal_window=signal_period
        )

        entries = macd.macd_crossed_above(macd.signal)
        exits = macd.macd_crossed_below(macd.signal)

        return entries, exits

    def _ema_macd_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """EMA + MACD strategy signals."""
        close = ohlcv["close"]
        short_ema = params.get("shortEmaPeriod", 12)
        long_ema = params.get("longEmaPeriod", 26)
        signal_period = params.get("signalPeriod", 9)

        ema_short = self.registry.create("EMA", close, ohlcv, {"period": short_ema})
        ema_long = self.registry.create("EMA", close, ohlcv, {"period": long_ema})
        macd = vbt.MACD.run(
            close,
            fast_window=short_ema,
            slow_window=long_ema,
            signal_window=signal_period,
        )

        # Entry: short EMA > long EMA and MACD > signal
        ema_bullish = ema_short > ema_long
        macd_bullish = macd.macd > macd.signal
        entries = ema_bullish.diff().fillna(False) & macd_bullish

        # Exit: short EMA < long EMA or MACD < signal
        ema_bearish = ema_short < ema_long
        macd_bearish = macd.macd < macd.signal
        exits = ema_bearish.diff().fillna(False) | (
            macd_bearish.diff().fillna(False) & macd_bearish
        )

        return entries.astype(bool), exits.astype(bool)

    def _sma_ema_crossover_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """SMA/EMA crossover strategy signals."""
        close = ohlcv["close"]
        sma_period = params.get("smaPeriod", 20)
        ema_period = params.get("emaPeriod", 10)

        sma = self.registry.create("SMA", close, ohlcv, {"period": sma_period})
        ema = self.registry.create("EMA", close, ohlcv, {"period": ema_period})

        entries = (ema.shift(1) <= sma.shift(1)) & (ema > sma)
        exits = (ema.shift(1) >= sma.shift(1)) & (ema < sma)

        return entries, exits

    def _rsi_ema_crossover_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """RSI + EMA strategy signals."""
        close = ohlcv["close"]
        rsi_period = params.get("rsiPeriod", 14)
        ema_period = params.get("emaPeriod", 20)

        rsi = self.registry.create("RSI", close, ohlcv, {"period": rsi_period})
        ema = self.registry.create("EMA", close, ohlcv, {"period": ema_period})

        # Entry: price crosses above EMA and RSI < 50
        price_cross_up = (close.shift(1) <= ema.shift(1)) & (close > ema)
        entries = price_cross_up & (rsi < 50)

        # Exit: price crosses below EMA or RSI > 70
        price_cross_down = (close.shift(1) >= ema.shift(1)) & (close < ema)
        exits = price_cross_down | (rsi > 70)

        return entries, exits

    def _bbands_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """Bollinger Bands mean reversion signals."""
        close = ohlcv["close"]
        period = params.get("period", 20)
        mult = params.get("multiplier", 2.0)

        lower = self.registry.create(
            "BOLLINGER_LOWER", close, ohlcv, {"period": period, "multiplier": mult}
        )
        middle = self.registry.create(
            "BOLLINGER_MIDDLE", close, ohlcv, {"period": period}
        )

        # Entry: price crosses below lower band
        entries = (close.shift(1) >= lower.shift(1)) & (close < lower)

        # Exit: price crosses above middle band
        exits = (close.shift(1) <= middle.shift(1)) & (close > middle)

        return entries, exits

    def _adx_stochastic_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """ADX + Stochastic strategy signals."""
        close = ohlcv["close"]
        adx_period = params.get("adxPeriod", 14)
        stoch_k = params.get("stochasticKPeriod", 14)
        oversold = params.get("oversoldThreshold", 20)
        overbought = params.get("overboughtThreshold", 80)

        adx = self.registry.create("ADX", close, ohlcv, {"period": adx_period})
        stoch = self.registry.create("STOCHASTIC_K", close, ohlcv, {"period": stoch_k})

        # Entry: ADX > 25 (trending) and stochastic crosses above oversold
        trending = adx > 25
        stoch_cross_up = (stoch.shift(1) <= oversold) & (stoch > oversold)
        entries = trending & stoch_cross_up

        # Exit: stochastic crosses below overbought
        stoch_cross_down = (stoch.shift(1) >= overbought) & (stoch < overbought)
        exits = stoch_cross_down

        return entries, exits

    def _double_ema_crossover_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """Double EMA crossover signals."""
        close = ohlcv["close"]
        short_period = params.get("shortEmaPeriod", 12)
        long_period = params.get("longEmaPeriod", 26)

        short_ema = self.registry.create("EMA", close, ohlcv, {"period": short_period})
        long_ema = self.registry.create("EMA", close, ohlcv, {"period": long_period})

        entries = (short_ema.shift(1) <= long_ema.shift(1)) & (short_ema > long_ema)
        exits = (short_ema.shift(1) >= long_ema.shift(1)) & (short_ema < long_ema)

        return entries, exits

    def _triple_ema_crossover_signals(
        self, ohlcv: pd.DataFrame, params: Dict
    ) -> Tuple[pd.Series, pd.Series]:
        """Triple EMA crossover signals."""
        close = ohlcv["close"]
        short_period = params.get("shortEmaPeriod", 5)
        medium_period = params.get("mediumEmaPeriod", 13)
        long_period = params.get("longEmaPeriod", 21)

        short_ema = self.registry.create("EMA", close, ohlcv, {"period": short_period})
        medium_ema = self.registry.create(
            "EMA", close, ohlcv, {"period": medium_period}
        )
        long_ema = self.registry.create("EMA", close, ohlcv, {"period": long_period})

        # Entry: all EMAs aligned bullish
        bullish = (short_ema > medium_ema) & (medium_ema > long_ema)
        entries = bullish & ~bullish.shift(1).fillna(False)

        # Exit: short crosses below medium
        exits = (short_ema.shift(1) >= medium_ema.shift(1)) & (short_ema < medium_ema)

        return entries, exits

    # Metric calculations
    def _calc_cumulative_return(self, portfolio: vbt.Portfolio) -> float:
        try:
            return float(portfolio.total_return())
        except Exception:
            return 0.0

    def _calc_annualized_return(self, portfolio: vbt.Portfolio, num_bars: int) -> float:
        try:
            total_return = portfolio.total_return()
            years = num_bars / self._bars_per_year
            if years <= 0:
                return 0.0
            return float((1 + total_return) ** (1 / years) - 1)
        except Exception:
            return 0.0

    def _calc_sharpe_ratio(self, returns: pd.Series) -> float:
        try:
            if returns.std() == 0:
                return 0.0
            excess_returns = returns.mean() - self._risk_free_rate / self._bars_per_year
            return float(excess_returns / returns.std() * np.sqrt(self._bars_per_year))
        except Exception:
            return 0.0

    def _calc_sortino_ratio(self, returns: pd.Series) -> float:
        try:
            negative_returns = returns[returns < 0]
            if len(negative_returns) == 0 or negative_returns.std() == 0:
                return 0.0
            excess_returns = returns.mean() - self._risk_free_rate / self._bars_per_year
            return float(
                excess_returns / negative_returns.std() * np.sqrt(self._bars_per_year)
            )
        except Exception:
            return 0.0

    def _calc_max_drawdown(self, portfolio: vbt.Portfolio) -> float:
        try:
            return float(abs(portfolio.max_drawdown()))
        except Exception:
            return 0.0

    def _calc_volatility(self, returns: pd.Series) -> float:
        try:
            return float(returns.std())
        except Exception:
            return 0.0

    def _calc_win_rate(self, portfolio: vbt.Portfolio) -> float:
        try:
            trades = portfolio.trades.records_readable
            if len(trades) == 0:
                return 0.0
            winning = len(trades[trades["PnL"] > 0])
            return float(winning / len(trades))
        except Exception:
            return 0.0

    def _calc_profit_factor(self, portfolio: vbt.Portfolio) -> float:
        try:
            trades = portfolio.trades.records_readable
            if len(trades) == 0:
                return 0.0
            gross_profit = trades[trades["PnL"] > 0]["PnL"].sum()
            gross_loss = abs(trades[trades["PnL"] < 0]["PnL"].sum())
            if gross_loss == 0:
                return float("inf") if gross_profit > 0 else 0.0
            return float(gross_profit / gross_loss)
        except Exception:
            return 0.0

    def _calc_num_trades(self, portfolio: vbt.Portfolio) -> int:
        try:
            return int(portfolio.trades.count())
        except Exception:
            return 0

    def _calc_avg_trade_duration(self, portfolio: vbt.Portfolio) -> float:
        try:
            trades = portfolio.trades.records_readable
            if len(trades) == 0:
                return 0.0
            durations = trades["Exit Index"] - trades["Entry Index"]
            return float(durations.mean())
        except Exception:
            return 0.0

    def _with_strategy_score(self, metrics: BacktestMetrics) -> BacktestMetrics:
        """Calculate and add strategy score."""

        def normalize(
            value: float, min_val: float = -1.0, max_val: float = 2.0
        ) -> float:
            return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

        score = (
            0.25 * normalize(metrics.sharpe_ratio)
            + 0.20 * (1 - metrics.max_drawdown)
            + 0.20 * metrics.win_rate
            + 0.20 * normalize(metrics.annualized_return)
            + 0.15 * normalize(metrics.profit_factor)
        )

        return BacktestMetrics(
            cumulative_return=metrics.cumulative_return,
            annualized_return=metrics.annualized_return,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown=metrics.max_drawdown,
            volatility=metrics.volatility,
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor,
            number_of_trades=metrics.number_of_trades,
            average_trade_duration=metrics.average_trade_duration,
            alpha=metrics.alpha,
            beta=metrics.beta,
            strategy_score=score,
        )
