package com.verlumen.tradestream.strategies;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.GAServiceClient;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.signals.TradeSignal;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.ta4j.core.Strategy;

/**
 * Core implementation of the Strategy Engine that coordinates strategy optimization, candlestick
 * processing, and trade signal generation.
 */
final class StrategyEngineImpl implements StrategyEngine {
  private final CandleBuffer candleBuffer;
  private final GAServiceClient gaClient;
  private final StrategyManager strategyManager;
  private final TradeSignalPublisher signalPublisher;

  // Thread-safe state management
  private final ConcurrentHashMap<StrategyType, StrategyRecord> strategyRecords =
      new ConcurrentHashMap<>();
  private volatile StrategyType currentStrategyType;
  private volatile Strategy currentStrategy;
  private volatile TradeSignal lastSignal =
      TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.NONE).build();

  @Inject
  StrategyEngineImpl(
      CandleBuffer candleBuffer,
      GAServiceClient gaClient,
      StrategyManager strategyManager,
      TradeSignalPublisher signalPublisher) {
    this.candleBuffer = candleBuffer;
    this.gaClient = gaClient;
    this.strategyManager = strategyManager;
    this.signalPublisher = signalPublisher;
    initializeStrategyRecords();
  }

  private void initializeStrategyRecords() {
    // Initialize records for all supported strategy types
    for (StrategyType type : StrategyType.values()) {
      strategyRecords.put(type, new StrategyRecord(type, null, Double.NEGATIVE_INFINITY));
    }

    // Set default strategy
    this.currentStrategyType = StrategyType.SMA_RSI;
    try {
      currentStrategy =
          strategyManager.createStrategy(
              candleBuffer.toBarSeries(),
              currentStrategyType,
              strategyManager.getInitialParameters(currentStrategyType));
    } catch (Exception e) {
      throw new RuntimeException("Failed to initialize default strategy", e);
    }
  }

  @Override
  public synchronized void handleCandle(Candle candle) {
    checkNotNull(candle, "Candle cannot be null");

    // Update market data
    candleBuffer.add(candle);

    // Check if optimization is needed
    if (shouldOptimize()) {
      optimizeAndSelectBestStrategy();
    }

    // Generate and publish trade signal
    TradeSignal signal = generateTradeSignal(candle);
    if (signal.getType() != TradeSignal.TradeSignalType.NONE) {
      signalPublisher.publish(signal);
    }

    lastSignal = signal;
  }

  @Override
  public synchronized void optimizeStrategy() {
    optimizeAndSelectBestStrategy();
  }

  @Override
  public Strategy getCurrentStrategy() {
    return currentStrategy;
  }

  private void optimizeAndSelectBestStrategy() {
    // Optimize all strategy types
    for (StrategyType strategyType : strategyRecords.keySet()) {
      GAOptimizationRequest request =
          GAOptimizationRequest.newBuilder()
              .setStrategyType(strategyType)
              .addAllCandles(candleBuffer.getCandles())
              .build();

      try {
        BestStrategyResponse response = gaClient.requestOptimization(request);
        updateStrategyRecord(
            strategyType, response.getBestStrategyParameters(), response.getBestScore());
      } catch (Exception e) {
        // Log error but continue with other strategies
        // TODO: Add proper logging
        continue;
      }
    }

    // Select the best performing strategy
    selectBestStrategy();
  }

  private void updateStrategyRecord(
      StrategyType strategyType, com.google.protobuf.Any parameters, double score) {
    strategyRecords.put(strategyType, new StrategyRecord(strategyType, parameters, score));
  }

  private void selectBestStrategy() {
    // Find strategy record with highest score
    StrategyRecord bestRecord =
        strategyRecords.values().stream()
            .max((r1, r2) -> Double.compare(r1.score(), r2.score()))
            .orElseThrow(() -> new IllegalStateException("No optimized strategies found"));

    // Update current strategy if different
    if (bestRecord.strategyType() != currentStrategyType) {
      try {
        Strategy newStrategy =
            strategyManager.createStrategy(
                candleBuffer.toBarSeries(), bestRecord.strategyType(), bestRecord.parameters());

        // Update atomically
        currentStrategyType = bestRecord.strategyType();
        currentStrategy = newStrategy;
      } catch (Exception e) {
        // Log error but maintain current strategy
        // TODO: Add proper logging
      }
    }
  }

  private boolean shouldOptimize() {
    // Optimize after SELL signals or if no active position
    return lastSignal.getType() == TradeSignal.TradeSignalType.SELL
        || lastSignal.getType() == TradeSignal.TradeSignalType.NONE;
  }

  private TradeSignal generateTradeSignal(Candle candle) {
    try {
      // Use current strategy to evaluate conditions
      int index = candleBuffer.getSize() - 1;

      if (currentStrategy.shouldEnter(index)) {
        return TradeSignal.newBuilder()
            .setType(TradeSignal.TradeSignalType.BUY)
            .setPrice(candle.getClose())
            .setTimestamp(candle.getTimestamp())
            .build();
      }

      if (currentStrategy.shouldExit(index)) {
        return TradeSignal.newBuilder()
            .setType(TradeSignal.TradeSignalType.SELL)
            .setPrice(candle.getClose())
            .setTimestamp(candle.getTimestamp())
            .build();
      }

      return TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.NONE).build();

    } catch (Exception e) {
      // Log error but avoid trading on errors
      // TODO: Add proper logging
      return TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.NONE).build();
    }
  }

  /** Immutable record of a strategy's current state and performance. */
  private record StrategyRecord(
      StrategyType strategyType, com.google.protobuf.Any parameters, double score) {
    StrategyRecord {
      checkNotNull(strategyType, "Strategy type cannot be null");
    }
  }
}
