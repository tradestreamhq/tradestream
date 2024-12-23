package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.ParameterizedBacktestRequest;
import com.verlumen.tradestream.backtesting.ParameterizedBacktestServiceGrpc;
import io.grpc.stub.StreamObserver;

public final class ParameterizedBacktestServiceImpl
    extends ParameterizedBacktestServiceGrpc.ParameterizedBacktestServiceImplBase {
  private final StrategyManager strategyManager;
  private final BacktestRunner backtestRunner;

  @Inject
  public ParameterizedBacktestServiceImpl(
      StrategyManager strategyManager,
      BacktestRunner backtestRunner) {
    this.strategyManager = strategyManager;
    this.backtestRunner = backtestRunner;
  }

  @Override
  public void runParameterizedBacktest(
      ParameterizedBacktestRequest request,
      StreamObserver<BacktestResult> responseObserver
  ) {

    }
  }
}
