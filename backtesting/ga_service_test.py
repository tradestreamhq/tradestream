# ga_service_test.py
import pytest
import grpc
import grpc_testing
from datetime import datetime

from protos.backtesting_pb2 import (
    BacktestRequest,
    ParameterizedBacktestRequest,
    BacktestResult,
    TimeframeResult
)
from protos.strategies_pb2 import StrategyType
from protos.marketdata_pb2 import Candle

from backtesting.ga_service import GAService

class TestGAService:
    @pytest.fixture
    def service(self):
        return GAService("localhost:50052")

    @pytest.fixture
    def sample_candles(self):
        candles = []
        timestamp = int(datetime(2024, 1, 1).timestamp() * 1000)
        for i in range(100):
            candle = Candle(
                timestamp=timestamp + i*60000,  # 1 minute intervals
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000.0
            )
            candles.append(candle)
        return candles

    @pytest.fixture
    def mock_backtest_result(self):
        return BacktestResult(
            strategy_type=StrategyType.SMA_RSI,
            timeframe_results=[
                TimeframeResult(
                    timeframe="1h",
                    cumulative_return=0.15,
                    annualized_return=0.30,
                    sharpe_ratio=1.5,
                    sortino_ratio=2.0,
                    max_drawdown=0.10,
                    win_rate=0.65,
                    profit_factor=1.8
                )
            ],
            overall_score=0.75
        )

    def test_optimize_strategy_sma_rsi(self, service, sample_candles, mock_backtest_result, mocker):
        # Mock the gRPC stub
        mock_stub = mocker.patch.object(service, 'parameterized_stub')
        mock_stub.RunParameterizedBacktest.return_value = mock_backtest_result

        # Create request
        request = BacktestRequest(
            candles=sample_candles,
            strategy_type=StrategyType.SMA_RSI
        )

        # Run optimization
        result = service.optimize_strategy(request, n_trials=5)

        # Verify stub was called with correct parameter ranges
        calls = mock_stub.RunParameterizedBacktest.call_args_list
        for call in calls:
            args, _ = call
            param_request = args[0]
            assert isinstance(param_request, ParameterizedBacktestRequest)
            assert param_request.strategy_type == StrategyType.SMA_RSI
            assert param_request.candles == sample_candles

        # Verify final result
        assert result == mock_backtest_result

    def test_optimize_strategy_unsupported_type(self, service, sample_candles):
        request = BacktestRequest(
            candles=sample_candles,
            strategy_type=999  # Invalid type
        )
        with pytest.raises(ValueError, match="Unsupported strategy type"):
            service.optimize_strategy(request)

    def test_optimize_strategy_grpc_error(self, service, sample_candles, mocker):
        # Mock gRPC error
        mock_stub = mocker.patch.object(service, 'parameterized_stub')
        mock_stub.RunParameterizedBacktest.side_effect = grpc.RpcError()

        request = BacktestRequest(
            candles=sample_candles,
            strategy_type=StrategyType.SMA_RSI
        )

        # Should complete but return suboptimal score
        result = service.optimize_strategy(request, n_trials=2)
        assert result.overall_score < 0

if __name__ == '__main__':
    pytest.main([__file__])
