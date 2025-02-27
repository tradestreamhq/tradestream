package com.verlumen.tradestream.pipeline.strategies;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategyManager;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;

import java.io.Serializable;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Maintains the state for the current strategy and records for all available strategies.
 * This class is serializable to support Beam state APIs.
 */
public class StrategyState implements Serializable {
  private final Map<StrategyType, StrategyRecord> strategyRecords;
  private StrategyType currentStrategyType;
  private transient org.ta4j.core.Strategy currentStrategy;
  
  // Strategy state can be initialized with empty records, or with predefined records
  private StrategyState(Map<StrategyType, StrategyRecord> strategyRecords,
                        StrategyType currentStrategyType) {
    this.strategyRecords = strategyRecords;
    this.currentStrategyType = currentStrategyType;
    // Note: currentStrategy is transient and will be reconstructed as needed
  }
  
  // Initialize with default parameters from the StrategyManager
  public static StrategyState initialize(StrategyManager strategyManager, BarSeries series) {
    Map<StrategyType, StrategyRecord> records = new ConcurrentHashMap<>();
    for (StrategyType type : strategyManager.getStrategyTypes()) {
      records.put(type, new StrategyRecord(type, 
          strategyManager.getDefaultParameters(type), Double.NEGATIVE_INFINITY));
    }
    
    StrategyType defaultType = StrategyType.SMA_RSI;
    StrategyState state = new StrategyState(records, defaultType);
    
    // Initialize the current strategy
    try {
      state.currentStrategy = strategyManager.createStrategy(series, defaultType);
    } catch (Exception e) {
      throw new RuntimeException("Failed to initialize default strategy", e);
    }
    
    return state;
  }
  
  // Reconstruct the current strategy if needed (e.g., after deserialization)
  public org.ta4j.core.Strategy getCurrentStrategy(StrategyManager strategyManager, 
                                                 BarSeries series) 
                                                 throws InvalidProtocolBufferException {
    if (currentStrategy == null) {
      StrategyRecord record = strategyRecords.get(currentStrategyType);
      currentStrategy = strategyManager.createStrategy(
          series, currentStrategyType, record.parameters());
    }
    return currentStrategy;
  }
  
  public void updateRecord(StrategyType type, Any parameters, double score) {
    strategyRecords.put(type, new StrategyRecord(type, parameters, score));
  }
  
  public StrategyState selectBestStrategy(StrategyManager strategyManager, BarSeries series) {
    StrategyRecord bestRecord = strategyRecords.values().stream()
        .max((r1, r2) -> Double.compare(r1.score(), r2.score()))
        .orElseThrow(() -> new IllegalStateException("No optimized strategy found"));
    
    this.currentStrategyType = bestRecord.strategyType();
    try {
      this.currentStrategy = strategyManager.createStrategy(
          series, currentStrategyType, bestRecord.parameters());
    } catch (Exception e) {
      throw new RuntimeException("Failed to create strategy", e);
    }
    
    return this;
  }
  
  public Strategy toStrategyMessage() {
    StrategyRecord record = strategyRecords.get(currentStrategyType);
    return Strategy.newBuilder()
        .setType(currentStrategyType)
        .setParameters(record.parameters())
        .build();
  }
  
  public Iterable<StrategyType> getStrategyTypes() {
    return strategyRecords.keySet();
  }
  
  public StrategyType getCurrentStrategyType() {
    return currentStrategyType;
  }
}
