"""
gRPC Backtesting Service Implementation.

Provides the gRPC interface for the VectorBT backtesting engine.
"""

import logging
import os
from concurrent import futures
from typing import Any, Dict, List

import grpc
import numpy as np
import pandas as pd

from protos import backtesting_pb2, marketdata_pb2, strategies_pb2
from services.shared.strategy_parameter_registry import unpack_strategy_parameters
from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner
from services.backtesting.walk_forward import (
    WalkForwardConfig,
    WalkForwardOptimizer,
    WalkForwardResult as WFResult,
)
from services.backtesting.monte_carlo import MonteCarloSimulator
from services.backtesting.portfolio_backtest import (
    PortfolioBacktester,
    StrategyAllocation,
)

logger = logging.getLogger(__name__)

# Service name and method descriptors for generic handler
SERVICE_NAME = "backtesting.BacktestingService"


class BacktestingServicer:
    """
    gRPC Servicer for the Backtesting service.

    Implements RunBacktest, RunBatchBacktest, RunWalkForwardValidation,
    RunMonteCarloSimulation, and RunPortfolioBacktest RPCs.
    """

    def __init__(self):
        self.runner = VectorBTRunner()
        self.walk_forward = WalkForwardOptimizer(self.runner)
        self.monte_carlo = MonteCarloSimulator(self.runner)
        self.portfolio_backtester = PortfolioBacktester(self.runner)
        self._warm_up_numba()

    def _warm_up_numba(self):
        """Pre-warm Numba JIT compilation to avoid first-call latency."""
        logger.info("Warming up Numba JIT compilation...")
        try:
            dummy_ohlcv = pd.DataFrame(
                {
                    "open": np.random.randn(100) + 100,
                    "high": np.random.randn(100) + 101,
                    "low": np.random.randn(100) + 99,
                    "close": np.random.randn(100) + 100,
                    "volume": np.random.randint(1000, 10000, 100).astype(float),
                }
            )
            entry = pd.Series([False] * 100)
            entry.iloc[10] = True
            exit_sig = pd.Series([False] * 100)
            exit_sig.iloc[20] = True
            self.runner.run_backtest(dummy_ohlcv, entry, exit_sig)
            logger.info("Numba warm-up complete")
        except Exception as e:
            logger.warning(f"Numba warm-up failed: {e}")

    def RunBacktest(
        self,
        request: backtesting_pb2.BacktestRequest,
        context: grpc.ServicerContext,
    ) -> backtesting_pb2.BacktestResult:
        """Run a single backtest."""
        try:
            ohlcv = self._candles_to_dataframe(request.candles)
            strategy_name = request.strategy.strategy_name
            parameters = self._extract_parameters(request.strategy)

            if not strategy_name:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("strategy_name is required")
                return backtesting_pb2.BacktestResult()

            metrics = self.runner.run_strategy(ohlcv, strategy_name, parameters)
            return self._metrics_to_proto(metrics)

        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return backtesting_pb2.BacktestResult()
        except Exception as e:
            logger.exception("Backtest failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Backtest failed: {e}")
            return backtesting_pb2.BacktestResult()

    def RunBatchBacktest(
        self,
        request: backtesting_pb2.BatchBacktestRequest,
        context: grpc.ServicerContext,
    ) -> backtesting_pb2.BatchBacktestResult:
        """Run multiple backtests with different parameter sets."""
        try:
            ohlcv = self._candles_to_dataframe(request.candles)
            strategy_name = request.strategy_name

            if not strategy_name:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("strategy_name is required")
                return backtesting_pb2.BatchBacktestResult()

            parameter_sets = [
                self._extract_parameters(strategy) for strategy in request.strategies
            ]

            results = self.runner.run_batch(ohlcv, strategy_name, parameter_sets)

            response = backtesting_pb2.BatchBacktestResult()
            for metrics in results:
                response.results.append(self._metrics_to_proto(metrics))
            return response

        except Exception as e:
            logger.exception("Batch backtest failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Batch backtest failed: {e}")
            return backtesting_pb2.BatchBacktestResult()

    def RunWalkForwardValidation(
        self,
        request: backtesting_pb2.WalkForwardRequest,
        context: grpc.ServicerContext,
    ) -> backtesting_pb2.WalkForwardResult:
        """Run walk-forward validation to detect overfitting."""
        try:
            ohlcv = self._candles_to_dataframe(request.candles)
            strategy_name = request.strategy.strategy_name
            parameters = self._extract_parameters(request.strategy)

            config = WalkForwardConfig(
                train_window_bars=request.config.train_window_bars or 6480,
                test_window_bars=request.config.test_window_bars or 2160,
                step_bars=request.config.step_bars or 2160,
                min_windows=request.config.min_windows or 4,
            )

            result = self.walk_forward.run(ohlcv, strategy_name, parameters, config)
            return self._wf_result_to_proto(result)

        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return backtesting_pb2.WalkForwardResult()
        except Exception as e:
            logger.exception("Walk-forward validation failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Walk-forward validation failed: {e}")
            return backtesting_pb2.WalkForwardResult()

    def RunMonteCarloSimulation(
        self,
        request: backtesting_pb2.MonteCarloRequest,
        context: grpc.ServicerContext,
    ) -> backtesting_pb2.MonteCarloResult:
        """Run Monte Carlo simulation."""
        try:
            ohlcv = self._candles_to_dataframe(request.candles)
            strategy_name = request.strategy.strategy_name
            parameters = self._extract_parameters(request.strategy)
            num_sims = request.num_simulations or 1000
            confidence = request.confidence_level or 0.95
            seed = request.random_seed

            result = self.monte_carlo.run(
                ohlcv,
                strategy_name,
                parameters,
                num_simulations=num_sims,
                confidence_level=confidence,
                random_seed=seed,
            )

            return backtesting_pb2.MonteCarloResult(
                original_result=self._metrics_to_proto(result.original_result),
                median_result=self._metrics_to_proto(result.median_result),
                worst_case_result=self._metrics_to_proto(result.worst_case_result),
                best_case_result=self._metrics_to_proto(result.best_case_result),
                num_simulations=result.num_simulations,
                confidence_level=result.confidence_level,
                probability_of_profit=result.probability_of_profit,
                expected_max_drawdown=result.expected_max_drawdown,
                expected_sharpe=result.expected_sharpe,
                sharpe_std_dev=result.sharpe_std_dev,
                return_distribution=result.return_distribution,
                drawdown_distribution=result.drawdown_distribution,
            )

        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return backtesting_pb2.MonteCarloResult()
        except Exception as e:
            logger.exception("Monte Carlo simulation failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Monte Carlo simulation failed: {e}")
            return backtesting_pb2.MonteCarloResult()

    def RunPortfolioBacktest(
        self,
        request: backtesting_pb2.PortfolioBacktestRequest,
        context: grpc.ServicerContext,
    ) -> backtesting_pb2.PortfolioBacktestResult:
        """Run portfolio-level backtest with multiple strategies."""
        try:
            ohlcv = self._candles_to_dataframe(request.candles)
            allocations = []
            for alloc in request.allocations:
                strategy_name = alloc.strategy.strategy_name
                parameters = self._extract_parameters(alloc.strategy)
                allocations.append(
                    StrategyAllocation(
                        strategy_name=strategy_name,
                        parameters=parameters,
                        weight=alloc.weight,
                    )
                )

            initial_capital = request.initial_capital or 10000.0
            rebalance_freq = request.rebalance_frequency_bars

            result = self.portfolio_backtester.run(
                ohlcv, allocations, initial_capital, rebalance_freq
            )

            strategy_results = []
            for sr in result.strategy_results:
                strategy_results.append(
                    backtesting_pb2.StrategyResult(
                        strategy_name=sr.strategy_name,
                        weight=sr.weight,
                        result=self._metrics_to_proto(sr.result),
                        return_contribution=sr.return_contribution,
                        risk_contribution=sr.risk_contribution,
                    )
                )

            return backtesting_pb2.PortfolioBacktestResult(
                portfolio_result=self._metrics_to_proto(result.portfolio_result),
                strategy_results=strategy_results,
                correlation_matrix=result.correlation_matrix,
                num_strategies=result.num_strategies,
                diversification_ratio=result.diversification_ratio,
            )

        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return backtesting_pb2.PortfolioBacktestResult()
        except Exception as e:
            logger.exception("Portfolio backtest failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Portfolio backtest failed: {e}")
            return backtesting_pb2.PortfolioBacktestResult()

    def _candles_to_dataframe(
        self, candles: List[marketdata_pb2.Candle]
    ) -> pd.DataFrame:
        """Convert proto candles to pandas DataFrame."""
        data = []
        for candle in candles:
            data.append(
                {
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
            )

        df = pd.DataFrame(data)
        df.index = pd.date_range(start="2020-01-01", periods=len(df), freq="1min")
        return df

    def _extract_parameters(self, strategy: strategies_pb2.Strategy) -> Dict[str, Any]:
        """Extract parameters from Strategy proto."""
        return unpack_strategy_parameters(strategy)

    def _metrics_to_proto(
        self, metrics: BacktestMetrics
    ) -> backtesting_pb2.BacktestResult:
        """Convert BacktestMetrics to proto message."""
        return backtesting_pb2.BacktestResult(
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
            strategy_score=metrics.strategy_score,
        )

    def _wf_result_to_proto(
        self, result: WFResult
    ) -> backtesting_pb2.WalkForwardResult:
        """Convert WalkForwardResult to proto message."""
        status_map = {
            "APPROVED": backtesting_pb2.APPROVED,
            "REJECTED": backtesting_pb2.REJECTED,
            "INSUFFICIENT_DATA": backtesting_pb2.INSUFFICIENT_DATA,
        }

        window_results = []
        for wr in result.window_results:
            window_results.append(
                backtesting_pb2.WindowResult(
                    window_index=wr.window_index,
                    in_sample_result=self._metrics_to_proto(wr.in_sample_result),
                    out_of_sample_result=self._metrics_to_proto(
                        wr.out_of_sample_result
                    ),
                    train_start_bar=wr.train_start_bar,
                    train_end_bar=wr.train_end_bar,
                    test_start_bar=wr.test_start_bar,
                    test_end_bar=wr.test_end_bar,
                )
            )

        return backtesting_pb2.WalkForwardResult(
            status=status_map.get(
                result.status, backtesting_pb2.VALIDATION_STATUS_UNSPECIFIED
            ),
            rejection_reason=result.rejection_reason,
            windows_count=result.windows_count,
            in_sample_sharpe=result.in_sample_sharpe,
            out_of_sample_sharpe=result.out_of_sample_sharpe,
            sharpe_degradation=result.sharpe_degradation,
            oos_sharpe_std_dev=result.oos_sharpe_std_dev,
            window_results=window_results,
            in_sample_return=result.in_sample_return,
            out_of_sample_return=result.out_of_sample_return,
            return_degradation=result.return_degradation,
        )


class BacktestingServiceHandler(grpc.GenericRpcHandler):
    """
    Generic RPC handler for BacktestingService.

    This allows us to implement the service without generated _pb2_grpc stubs.
    """

    def __init__(self, servicer: BacktestingServicer):
        self.servicer = servicer
        self._method_handlers = {
            f"/{SERVICE_NAME}/RunBacktest": grpc.unary_unary_rpc_method_handler(
                servicer.RunBacktest,
                request_deserializer=backtesting_pb2.BacktestRequest.FromString,
                response_serializer=backtesting_pb2.BacktestResult.SerializeToString,
            ),
            f"/{SERVICE_NAME}/RunBatchBacktest": grpc.unary_unary_rpc_method_handler(
                servicer.RunBatchBacktest,
                request_deserializer=backtesting_pb2.BatchBacktestRequest.FromString,
                response_serializer=backtesting_pb2.BatchBacktestResult.SerializeToString,
            ),
            f"/{SERVICE_NAME}/RunWalkForwardValidation": grpc.unary_unary_rpc_method_handler(
                servicer.RunWalkForwardValidation,
                request_deserializer=backtesting_pb2.WalkForwardRequest.FromString,
                response_serializer=backtesting_pb2.WalkForwardResult.SerializeToString,
            ),
            f"/{SERVICE_NAME}/RunMonteCarloSimulation": grpc.unary_unary_rpc_method_handler(
                servicer.RunMonteCarloSimulation,
                request_deserializer=backtesting_pb2.MonteCarloRequest.FromString,
                response_serializer=backtesting_pb2.MonteCarloResult.SerializeToString,
            ),
            f"/{SERVICE_NAME}/RunPortfolioBacktest": grpc.unary_unary_rpc_method_handler(
                servicer.RunPortfolioBacktest,
                request_deserializer=backtesting_pb2.PortfolioBacktestRequest.FromString,
                response_serializer=backtesting_pb2.PortfolioBacktestResult.SerializeToString,
            ),
        }

    def service(self, handler_call_details):
        """Return the handler for the given method."""
        return self._method_handlers.get(handler_call_details.method)


def create_grpc_server(port: int = 50051) -> grpc.Server:
    """Create and configure the gRPC server.

    When TLS_CERT_PATH and TLS_KEY_PATH environment variables are set,
    the server uses TLS encryption. Otherwise, it falls back to an
    insecure port for local development.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = BacktestingServicer()
    server.add_generic_rpc_handlers((BacktestingServiceHandler(servicer),))

    cert_path = os.environ.get("TLS_CERT_PATH")
    key_path = os.environ.get("TLS_KEY_PATH")

    if cert_path and key_path:
        with open(cert_path, "rb") as f:
            cert_pem = f.read()
        with open(key_path, "rb") as f:
            key_pem = f.read()
        server_credentials = grpc.ssl_server_credentials([(key_pem, cert_pem)])
        server.add_secure_port(f"[::]:{port}", server_credentials)
        logger.info("gRPC server configured with TLS (cert=%s)", cert_path)
    else:
        server.add_insecure_port(f"[::]:{port}")
        logger.warning(
            "TLS not configured (TLS_CERT_PATH and TLS_KEY_PATH not set). "
            "Using insecure port."
        )

    return server
