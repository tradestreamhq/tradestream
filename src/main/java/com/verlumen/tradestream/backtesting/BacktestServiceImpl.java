package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestServiceGrpc;
import com.verlumen.tradestream.strategies.StrategyManager;
import com.verlumen.tradestream.marketdata.Candle;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

final class BacktestServiceImpl
    extends BacktestServiceGrpc.BacktestServiceImplBase {
  private final StrategyManager strategyManager;
  private final BacktestRunner backtestRunner;

  @Inject
  public BacktestServiceImpl(
      StrategyManager strategyManager,
      BacktestRunner backtestRunner) {
    this.strategyManager = strategyManager;
    this.backtestRunner = backtestRunner;
  }

  @Override
  public void runBacktest(
      BacktestRequest request,
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

    } catch (Exception e) {
      responseObserver.onError(
          Status.INTERNAL
              .withCause(e)
              .withDescription(e.getMessage())
              .asRuntimeException()
      );
    }
  }

  private BarSeries buildBarSeries(BacktestRequest request) {
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
