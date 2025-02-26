package com.verlumen.tradestream.strategies;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.signals.TradeSignal;
import com.verlumen.tradestream.signals.TradeSignalPublisher;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.ta4j.core.BarSeries;
import org.ta4j.core.TradingRecord;

/**
 * Core implementation of the Strategy Engine that coordinates strategy optimization, candlestick
 * processing, and trade signal generation.
 */
final class StrategyEngineImpl implements StrategyEngine {
  private final CandleBuffer candleBuffer;
  private final GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator;
  private final StrategyManager strategyManager;
  private final TradeSignalPublisher signalPublisher;

  // Thread-safe state management
  private final ConcurrentHashMap<StrategyType, StrategyRecord> strategyRecords =
      new ConcurrentHashMap<>();
  private volatile StrategyType currentStrategyType;
  private volatile org.ta4j.core.Strategy currentStrategy;
  private volatile TradeSignal lastSignal =
      TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.NONE).build();

  @Inject
  StrategyEngineImpl(
      CandleBuffer candleBuffer,
      GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator,
      StrategyManager strategyManager,
      TradeSignalPublisher signalPublisher) {
    this.candleBuffer = candleBuffer;
    this.geneticAlgorithmOrchestrator = geneticAlgorithmOrchestrator;
    this.strategyManager = strategyManager;
    this.signalPublisher = signalPublisher;
    initializeStrategyRecords();
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
  public org.ta4j.core.Strategy getCurrentStrategy() {
    return currentStrategy;
  }

  private void initializeStrategyRecords() {
    // Initialize records for all supported strategy types
    for (StrategyType type : strategyManager.getStrategyTypes()) {
      Any defaultParameters = strategyManager.getDefaultParameters(type);
      strategyRecords.put(type, new StrategyRecord(type, defaultParameters, Double.NEGATIVE_INFINITY));
    }

    // Set default strategy
    this.currentStrategyType = StrategyType.SMA_RSI;
    try {
      currentStrategy =
          strategyManager.createStrategy(candleBuffer.toBarSeries(), currentStrategyType);
    } catch (Exception e) {
      throw new RuntimeException("Failed to initialize default strategy", e);
    }
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
        BestStrategyResponse response = geneticAlgorithmOrchestrator.requestOptimization(request);
        Any any = response.getBestStrategyParameters();
        updateStrategyRecord(strategyType, any, response.getBestScore());
      } catch (Exception e) {
        // Log error but continue with other strategies
        // TODO: Add proper logging
        System.err.println(
            "Error during optimization for strategy type: "
                + strategyType
                + ". "
                + e.getMessage());
        continue;
      }
    }

    // Select the best performing strategy
    selectBestStrategy();
  }

  private void updateStrategyRecord(
      StrategyType strategyType, Any parameters, double score) {
    strategyRecords.put(strategyType, new StrategyRecord(strategyType, parameters, score));
  }

  private void selectBestStrategy() {
    // Find strategy record with highest score
    StrategyRecord bestRecord =
        strategyRecords.values().stream()
            .max((r1, r2) -> Double.compare(r1.score(), r2.score()))
            .orElseThrow(() -> new IllegalStateException("No optimized strategy found"));

    currentStrategyType = bestRecord.strategyType();
    try {
      currentStrategy =
          strategyManager.createStrategy(
                  candleBuffer.toBarSeries(), currentStrategyType, bestRecord.parameters());
    } catch (InvalidProtocolBufferException e) {
      throw new RuntimeException(e);
    }
  }

  private boolean shouldOptimize() {
    // Optimize after SELL signals or if no active position
    return lastSignal.getType() == TradeSignal.TradeSignalType.SELL
        || lastSignal.getType() == TradeSignal.TradeSignalType.NONE;
  }

  private TradeSignal generateTradeSignal(Candle candle) {
    BarSeries barSeries = candleBuffer.toBarSeries();
    int endIndex = barSeries.getEndIndex();
    
    TradeSignal.Builder signalBuilder = TradeSignal.newBuilder();
    
    try {
        if (currentStrategy.shouldEnter(endIndex)) {
            signalBuilder.setType(TradeSignal.TradeSignalType.BUY)
                .setTimestamp(candle.getTimestamp().getSeconds() * 1000)
                .setPrice(candle.getClose());
        } else if (currentStrategy.shouldExit(endIndex)) {
            signalBuilder.setType(TradeSignal.TradeSignalType.SELL)
                .setTimestamp(candle.getTimestamp().getSeconds() * 1000)
                .setPrice(candle.getClose());
        } else {
            signalBuilder.setType(TradeSignal.TradeSignalType.NONE);
        }

        // Convert the current TA4J strategy to a Strategy message
        Strategy strategyMessage = convertTa4jStrategy(currentStrategy, currentStrategyType);
        signalBuilder.setStrategy(strategyMessage);
    } catch (Exception e) {
        System.err.println("Error generating trade signal: " + e.getMessage());
        signalBuilder.setType(TradeSignal.TradeSignalType.ERROR)
            .setReason("Error generating trade signal: " + e.getMessage());
    }

    return signalBuilder.build();
  }

  private Strategy convertTa4jStrategy(org.ta4j.core.Strategy ta4jStrategy, StrategyType strategyType) {
      // Create a new Strategy message
      Strategy.Builder strategyMessageBuilder = Strategy.newBuilder();
    
      // Set the strategy type
      strategyMessageBuilder.setType(strategyType);
    
      // Set the parameters (if available)
      Any parameters = strategyRecords.get(strategyType).parameters();
      if (parameters != null) {
          strategyMessageBuilder.setParameters(parameters);
      }
    
      return strategyMessageBuilder.build();
  }

  /** Immutable record of a strategy's current state and performance */
  private record StrategyRecord(StrategyType strategyType, Any parameters, double score) {
    StrategyRecord {
      checkNotNull(strategyType, "Strategy type cannot be null");
    }
  }
}
