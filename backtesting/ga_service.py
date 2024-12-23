# ga_service.py
import grpc
import optuna
from concurrent import futures
from typing import List, Dict

from protos.backtesting_pb2 import (
    BacktestRequest, 
    ParameterizedBacktestRequest,
    BacktestResult,
    TimeframeResult
)
from protos.backtesting_pb2_grpc import (
    BacktestServiceStub,
    ParameterizedBacktestServiceStub
)
from protos.strategies_pb2 import StrategyType

class GAService:
    def __init__(self, ta4j_service_address: str):
        self.channel = grpc.insecure_channel(ta4j_service_address)
        self.backtest_stub = BacktestServiceStub(self.channel)
        self.parameterized_stub = ParameterizedBacktestServiceStub(self.channel)
        
    def optimize_strategy(self, request: BacktestRequest, n_trials: int = 100) -> BacktestResult:
        strategy_type = request.strategy_type
        
        def objective(trial):
            # Generate strategy parameters based on strategy type
            params = self._create_strategy_parameters(trial, strategy_type)
            
            # Create parameterized request
            param_request = ParameterizedBacktestRequest(
                candles=request.candles,
                strategy_type=strategy_type,
                strategy_parameters=params
            )
            
            # Run backtest and get results
            try:
                result = self.parameterized_stub.RunParameterizedBacktest(param_request)
                return result.overall_score
            except grpc.RpcError as e:
                print(f"Error running backtest: {e}")
                return float('-inf')
                
        # Create and run Optuna study
        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler()
        )
        study.optimize(objective, n_trials=n_trials)
        
        # Get best parameters and run final backtest
        best_params = self._create_strategy_parameters(study.best_trial, strategy_type)
        final_request = ParameterizedBacktestRequest(
            candles=request.candles,
            strategy_type=strategy_type,
            strategy_parameters=best_params
        )
        
        return self.parameterized_stub.RunParameterizedBacktest(final_request)
        
    def _create_strategy_parameters(self, trial: optuna.Trial, strategy_type: StrategyType) -> Any:
        if strategy_type == StrategyType.SMA_RSI:
            return Any(
                type_url="type.googleapis.com/backtesting.SmaRsiParameters",
                value=SmaRsiParameters(
                    moving_average_period=trial.suggest_int("ma_period", 5, 200),
                    rsi_period=trial.suggest_int("rsi_period", 5, 30),
                    overbought_threshold=trial.suggest_float("overbought", 70, 90),
                    oversold_threshold=trial.suggest_float("oversold", 10, 30)
                ).SerializeToString()
            )
        elif strategy_type == StrategyType.DOUBLE_EMA_CROSSOVER:
            return Any(
                type_url="type.googleapis.com/backtesting.DoubleEmaCrossoverParameters", 
                value=DoubleEmaCrossoverParameters(
                    short_ema_period=trial.suggest_int("short_period", 5, 50),
                    long_ema_period=trial.suggest_int("long_period", 51, 200)
                ).SerializeToString()
            )
        # Add other strategy types here
        else:
            raise ValueError(f"Unsupported strategy type: {strategy_type}")

def serve(host: str = "[::]:50051", ta4j_service_address: str = "localhost:50052"):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service = GAService(ta4j_service_address)
    add_BacktestServiceServicer_to_server(service, server)
    server.add_insecure_port(host)
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
