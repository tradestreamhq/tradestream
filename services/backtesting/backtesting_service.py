"""
gRPC Backtesting Service Implementation.

Provides the gRPC interface for the VectorBT backtesting engine.
"""

import logging
from typing import Dict, Any, List
from concurrent import futures
import pandas as pd
import numpy as np

# Generated protobuf imports (to be generated from .proto files)
# For now, we'll define a simple interface that can be adapted
from vectorbt_runner import VectorBTRunner, BacktestMetrics


logger = logging.getLogger(__name__)


class BacktestingServiceImpl:
    """
    Implementation of the Backtesting gRPC service.

    This service accepts BacktestRequest messages and returns BacktestResult messages.
    """

    def __init__(self):
        self.runner = VectorBTRunner()
        self._warm_up_numba()

    def _warm_up_numba(self):
        """Pre-warm Numba JIT compilation to avoid first-call latency."""
        logger.info("Warming up Numba JIT compilation...")
        try:
            # Create small dummy dataset
            dummy_ohlcv = pd.DataFrame(
                {
                    "open": np.random.randn(100) + 100,
                    "high": np.random.randn(100) + 101,
                    "low": np.random.randn(100) + 99,
                    "close": np.random.randn(100) + 100,
                    "volume": np.random.randint(1000, 10000, 100).astype(float),
                }
            )
            # Run a simple backtest to trigger JIT
            entry = pd.Series([False] * 100)
            entry.iloc[10] = True
            exit_sig = pd.Series([False] * 100)
            exit_sig.iloc[20] = True
            self.runner.run_backtest(dummy_ohlcv, entry, exit_sig)
            logger.info("Numba warm-up complete")
        except Exception as e:
            logger.warning(f"Numba warm-up failed: {e}")

    def run_backtest(self, request_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a backtest from a dictionary request (JSON-compatible).

        Args:
            request_dict: Dictionary containing:
                - candles: List of candle dictionaries with timestamp, open, high, low, close, volume
                - strategy: Dictionary with strategy_name and parameters

        Returns:
            Dictionary with backtest results
        """
        try:
            # Parse candles into DataFrame
            candles = request_dict.get("candles", [])
            if not candles:
                raise ValueError("No candles provided")

            ohlcv = self._candles_to_dataframe(candles)

            # Extract strategy info
            strategy = request_dict.get("strategy", {})
            strategy_name = strategy.get(
                "strategy_name", strategy.get("strategyName", "")
            )
            if not strategy_name:
                raise ValueError("No strategy name provided")

            # Extract parameters from Any field
            parameters = self._extract_parameters(strategy)

            # Run backtest
            metrics = self.runner.run_strategy(ohlcv, strategy_name, parameters)

            # Convert to response format
            return self._metrics_to_dict(metrics)

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise

    def run_batch_backtest(
        self,
        candles: List[Dict],
        strategy_name: str,
        parameter_sets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run multiple backtests with different parameter sets.

        Optimized for GA optimization use case.
        """
        ohlcv = self._candles_to_dataframe(candles)
        results = self.runner.run_batch(ohlcv, strategy_name, parameter_sets)
        return [self._metrics_to_dict(m) for m in results]

    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """Convert candle list to pandas DataFrame."""
        data = []
        for candle in candles:
            data.append(
                {
                    "open": float(candle.get("open", 0)),
                    "high": float(candle.get("high", 0)),
                    "low": float(candle.get("low", 0)),
                    "close": float(candle.get("close", 0)),
                    "volume": float(candle.get("volume", 0)),
                }
            )

        df = pd.DataFrame(data)
        df.index = pd.date_range(start="2020-01-01", periods=len(df), freq="1min")
        return df

    def _extract_parameters(self, strategy: Dict) -> Dict[str, Any]:
        """Extract strategy parameters from the strategy dict."""
        # Handle different parameter formats
        params = strategy.get("parameters", {})

        # If parameters is an Any-like structure with typeUrl and value
        if isinstance(params, dict) and "typeUrl" in params:
            # Extract from the nested structure
            # The actual values would be in a decoded protobuf, but for JSON
            # interface we expect them directly
            return params.get("value", {})

        # Direct parameter dict
        if isinstance(params, dict):
            return params

        return {}

    def _metrics_to_dict(self, metrics: BacktestMetrics) -> Dict[str, Any]:
        """Convert BacktestMetrics to dictionary."""
        return {
            "cumulativeReturn": metrics.cumulative_return,
            "annualizedReturn": metrics.annualized_return,
            "sharpeRatio": metrics.sharpe_ratio,
            "sortinoRatio": metrics.sortino_ratio,
            "maxDrawdown": metrics.max_drawdown,
            "volatility": metrics.volatility,
            "winRate": metrics.win_rate,
            "profitFactor": metrics.profit_factor,
            "numberOfTrades": metrics.number_of_trades,
            "averageTradeDuration": metrics.average_trade_duration,
            "alpha": metrics.alpha,
            "beta": metrics.beta,
            "strategyScore": metrics.strategy_score,
        }


# ============================================================================
# gRPC Server Implementation (when protobuf stubs are generated)
# ============================================================================


def create_grpc_server(port: int = 50051):
    """
    Create and configure the gRPC server.

    Note: This requires generated protobuf stubs. For initial testing,
    use the REST/JSON interface via main.py
    """
    try:
        import grpc
        # Generated stubs would be imported here:
        # from protos import backtesting_pb2, backtesting_pb2_grpc

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        # Add service implementation
        # backtesting_pb2_grpc.add_BacktestServiceServicer_to_server(
        #     BacktestingServiceImpl(), server
        # )
        server.add_insecure_port(f"[::]:{port}")
        return server
    except ImportError:
        logger.warning("gRPC stubs not generated. Use REST interface instead.")
        return None
