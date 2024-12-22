package com.verlumen.tradestream.strategies;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.BacktestServiceOuterClass.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestServiceOuterClass.ParameterizedBacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestServiceOuterClass.TimeframeResult;
import com.verlumen.tradestream.backtesting.ParameterizedBacktestServiceGrpc;
import com.verlumen.tradestream.marketdata.Marketdata;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.Map;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

public final class ParameterizedBacktestServiceImpl
    extends ParameterizedBacktestServiceGrpc.ParameterizedBacktestServiceImplBase {
  private final Map<StrategyType, StrategyFactory<?>> strategyFactories;

  @Inject
  public ParameterizedBacktestServiceImpl(Map<StrategyType, StrategyFactory<?>> strategyFactories) {
    this.strategyFactories = strategyFactories;
  }

  @Override
  public void runParameterizedBacktest(
      ParameterizedBacktestRequest request,
      StreamObserver<BacktestResult> responseObserver
  ) {
    try {
      // 1) Convert the repeated candles
      BarSeries series = buildBarSeries(request);

      // 2) Get the strategy type
      StrategyType strategyType = request.getStrategyType();

      // 3) Look up the factory
      StrategyFactory<?> factory = strategyFactories.get(strategyType);
      if (factory == null) {
        responseObserver.onError(
            Status.INVALID_ARGUMENT
                .withDescription("Unrecognized StrategyType: " + strategyType)
                .asRuntimeException()
        );
        return;
      }

      // 4) Unpack the strategy parameters from the request’s `Any` field
      //    E.g. request.getStrategyParameters() is an Any
      Any rawParams = request.getStrategyParameters();

      // Because each factory has a known parameter type T extends Message,
      // we can do “factory.createStrategy(series, rawParams)” and the default method
      // in StrategyFactory will do an Any#unpack(T). For example:
      Strategy strategy = factory.createStrategy(series, rawParams);

      // 5) Run your real backtest logic ...
      //    Below is a placeholder with random values
      double randomCumulativeReturn = Math.random();
      BacktestResult result = BacktestResult.newBuilder()
          .setStrategyType(strategyType)
          .addTimeframeResults(
              TimeframeResult.newBuilder()
                  .setTimeframe("ALL_DATA")
                  .setCumulativeReturn(randomCumulativeReturn)
                  .setAnnualizedReturn(randomCumulativeReturn * 1.5)
                  .setSharpeRatio(1.11)
                  .setSortinoRatio(0.95)
                  .setMaxDrawdown(0.20)
                  .setVolatility(0.07)
                  .setWinRate(0.60)
                  .setProfitFactor(1.85)
                  .setNumberOfTrades(22)
                  .setAverageTradeDuration(30.0)
                  .setAlpha(0.03)
                  .setBeta(0.40)
                  .build()
          )
          .setOverallScore(0.92)
          .build();

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
    for (Marketdata.Candle candle : request.getCandlesList()) {
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
