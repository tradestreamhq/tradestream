"""
Backtesting engine that replays historical market data against trading strategies.

Orchestrates data loading, strategy signal generation, trade simulation,
and performance metric calculation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from services.backtesting.data_loader import BacktestDataLoader
from services.backtesting.metrics import (
    PerformanceMetrics,
    Trade,
    calculate_metrics,
)
from services.backtesting.vectorbt_runner import VectorBTRunner

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    symbols: List[str]
    start: str  # RFC3339 or InfluxDB relative (e.g., "-30d")
    end: Optional[str] = None
    strategy_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeframe: str = "1m"
    initial_capital: float = 10000.0
    fee_rate: float = 0.001  # 0.1%


@dataclass
class SymbolResult:
    """Backtest result for a single symbol."""

    symbol: str
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: List[float]


@dataclass
class BacktestResult:
    """Aggregate result across all symbols in a backtest run."""

    config: BacktestConfig
    symbol_results: Dict[str, SymbolResult]
    aggregate_metrics: PerformanceMetrics


class BacktestEngine:
    """
    Engine that replays historical candle data against strategy implementations.

    Usage:
        loader = BacktestDataLoader(url, token, org, bucket)
        engine = BacktestEngine(data_loader=loader)

        config = BacktestConfig(
            symbols=["BTC/USD", "ETH/USD"],
            start="2024-01-01T00:00:00Z",
            end="2024-06-01T00:00:00Z",
            strategy_name="SMA_RSI",
            parameters={"movingAveragePeriod": 20, "rsiPeriod": 14},
        )
        result = engine.run(config)
        print(result.aggregate_metrics.sharpe_ratio)
    """

    def __init__(
        self,
        data_loader: Optional[BacktestDataLoader] = None,
        runner: Optional[VectorBTRunner] = None,
    ):
        self._data_loader = data_loader
        self._runner = runner or VectorBTRunner()

    def run(self, config: BacktestConfig) -> BacktestResult:
        """
        Run a backtest across all configured symbols.

        Args:
            config: BacktestConfig with symbols, date range, strategy, and parameters.

        Returns:
            BacktestResult with per-symbol and aggregate metrics.
        """
        logger.info(
            "Starting backtest: strategy=%s symbols=%s start=%s end=%s",
            config.strategy_name,
            config.symbols,
            config.start,
            config.end,
        )

        symbol_data = self._load_data(config)
        symbol_results = {}

        for symbol, ohlcv in symbol_data.items():
            logger.info(
                "Running backtest for %s (%d bars)", symbol, len(ohlcv)
            )
            result = self._run_symbol(symbol, ohlcv, config)
            symbol_results[symbol] = result

        aggregate = self._aggregate_results(symbol_results)

        logger.info(
            "Backtest complete: %d symbols, aggregate sharpe=%.3f, "
            "total_return=%.4f, max_drawdown=%.4f",
            len(symbol_results),
            aggregate.sharpe_ratio,
            aggregate.total_return,
            aggregate.max_drawdown,
        )

        return BacktestResult(
            config=config,
            symbol_results=symbol_results,
            aggregate_metrics=aggregate,
        )

    def run_with_data(
        self,
        config: BacktestConfig,
        symbol_data: Dict[str, pd.DataFrame],
    ) -> BacktestResult:
        """
        Run a backtest with pre-loaded data (useful for testing).

        Args:
            config: BacktestConfig with strategy name and parameters.
            symbol_data: Dict mapping symbol to OHLCV DataFrame.

        Returns:
            BacktestResult with per-symbol and aggregate metrics.
        """
        symbol_results = {}
        for symbol, ohlcv in symbol_data.items():
            result = self._run_symbol(symbol, ohlcv, config)
            symbol_results[symbol] = result

        aggregate = self._aggregate_results(symbol_results)
        return BacktestResult(
            config=config,
            symbol_results=symbol_results,
            aggregate_metrics=aggregate,
        )

    def _load_data(self, config: BacktestConfig) -> Dict[str, pd.DataFrame]:
        """Load market data for all symbols in the config."""
        if self._data_loader is None:
            raise RuntimeError(
                "No data_loader configured. Use run_with_data() for in-memory data "
                "or provide a BacktestDataLoader to the engine."
            )

        return self._data_loader.load_multiple_symbols(
            symbols=config.symbols,
            start=config.start,
            end=config.end,
            timeframe=config.timeframe,
        )

    def _run_symbol(
        self,
        symbol: str,
        ohlcv: pd.DataFrame,
        config: BacktestConfig,
    ) -> SymbolResult:
        """Run backtest for a single symbol."""
        # Generate entry/exit signals using VectorBT runner
        entry_signals, exit_signals = self._runner._generate_signals(
            ohlcv, config.strategy_name, config.parameters
        )

        # Simulate trades from signals
        trades = self._simulate_trades(
            ohlcv, entry_signals, exit_signals, symbol, config.fee_rate
        )

        # Calculate equity curve
        equity_curve = self._build_equity_curve(
            trades, config.initial_capital
        )

        # Calculate metrics
        metrics = calculate_metrics(trades)

        return SymbolResult(
            symbol=symbol,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
        )

    @staticmethod
    def _simulate_trades(
        ohlcv: pd.DataFrame,
        entries: pd.Series,
        exits: pd.Series,
        symbol: str,
        fee_rate: float,
    ) -> List[Trade]:
        """
        Simulate trades from entry/exit signal series.

        Walks through the signals sequentially: enters on entry signal,
        exits on exit signal. Only one position at a time.
        """
        trades = []
        close = ohlcv["close"].values
        entry_vals = entries.values
        exit_vals = exits.values
        in_position = False
        entry_price = 0.0
        entry_idx = 0

        for i in range(len(close)):
            if not in_position and entry_vals[i]:
                entry_price = close[i] * (1 + fee_rate)  # slippage on entry
                entry_idx = i
                in_position = True
            elif in_position and exit_vals[i]:
                exit_price = close[i] * (1 - fee_rate)  # slippage on exit
                trades.append(
                    Trade(
                        entry_price=entry_price,
                        exit_price=exit_price,
                        entry_index=entry_idx,
                        exit_index=i,
                        symbol=symbol,
                    )
                )
                in_position = False

        return trades

    @staticmethod
    def _build_equity_curve(
        trades: List[Trade], initial_capital: float
    ) -> List[float]:
        """Build an equity curve from a list of trades."""
        equity = [initial_capital]
        current = initial_capital

        for trade in trades:
            current *= 1 + trade.return_pct
            equity.append(current)

        return equity

    @staticmethod
    def _aggregate_results(
        symbol_results: Dict[str, SymbolResult],
    ) -> PerformanceMetrics:
        """Aggregate metrics across all symbols."""
        all_trades = []
        for result in symbol_results.values():
            all_trades.extend(result.trades)

        return calculate_metrics(all_trades)
