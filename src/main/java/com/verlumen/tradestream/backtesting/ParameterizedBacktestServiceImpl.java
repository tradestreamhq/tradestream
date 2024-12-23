package com.verlumen.tradestream.strategies;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.ParameterizedBacktestRequest;
import com.verlumen.tradestream.backtesting.ParameterizedBacktestServiceGrpc;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

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
    try {
      // Convert the repeated candles to a BarSeries
      BarSeries series = buildBarSeries(request);

      // Create strategy using manager
      Strategy strategy = strategyManager.createStrategy(
          series, 
          request.getStrategyType(), 
          request.getStrategyParameters());

      // Create backtest request
      BacktestRunner.BacktestRequest backtestRequest = BacktestRunner.BacktestRequest.builder()
          .setBarSeries(series)
          .setStrategy(strategy)
          .setStrategyType(request.getStrategyType())
          .build();

      // Run backtest and get results
      BacktestResult result = backtestRunner.runBacktest(backtestRequest);

      responseObserver.onNext(result);
      responseObserver.onCompleted();

    } catch (InvalidProtocolBufferException e) {
      responseObserver.onError(
          Status.INVALID_ARGUMENT
              .withCause(e)
              .withDescription("Failed to unpack strategy parameters: " + e.getMessage())
              .asRuntimeException()
      );
    } catch (Exception e) {
      responseObserver.onError(
          Status.INTERNAL
              .withCause(e)
              .withDescription(e.getMessage())
              .asRuntimeException()
      );
    }
  }

  private BarSeries buildBarSeries(ParameterizedBacktestRequest request) {
    BaseBarSeries series = new BaseBarSeries("param-backtest-series");
    ZonedDateTime now = ZonedDateTime.now();
    for (Candle candle : request.getCandlesList()) {
      Bar bar = new BaseBar(
          Duration.ofMinutes(1),
          now.plusMinutes(series.getBarCount()),
          candle.getOpen(),
          candle.getHigh(),
          candle.getLow(),
          candle.getClose(),
          candle.getVolume()
      );
      series.addBar(bar);
    }
    return series;
  }
}
