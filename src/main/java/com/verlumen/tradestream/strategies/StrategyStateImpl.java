package com.verlumen.tradestream.strategies;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.ta4j.core.BarSeries;

/**
 * Implementation of the StrategyState interface.
 * This class is serializable to support Beam state APIs.
 */
public class StrategyStateImpl implements StrategyState {
    private static final StrategyType DEFAULT_TYPE = StrategyType.SMA_RSI;

    private final StrategyManager strategyManager;
    private final Map<StrategyType, StrategyRecord> strategyRecords;
    private StrategyType currentStrategyType;
    private transient org.ta4j.core.Strategy currentStrategy;
    
    @Inject
    public StrategyStateImpl(StrategyManager strategyManager) {
        this.strategyManager = strategyManager;
        this.strategyRecords = new ConcurrentHashMap<>();
        
        // Initialize strategy records for all available strategy types
        for (StrategyType type : strategyManager.getStrategyTypes()) {
            strategyRecords.put(type, new StrategyRecord(
                type, 
                strategyManager.getDefaultParameters(type), 
                Double.NEGATIVE_INFINITY));
        }
        
        this.currentStrategyType = DEFAULT_TYPE;
        this.currentStrategy = null;
    }
    
    @Override
    public org.ta4j.core.Strategy getCurrentStrategy(BarSeries series)
            throws InvalidProtocolBufferException {
        if (currentStrategy == null) {
            StrategyRecord record = strategyRecords.get(currentStrategyType);
            if (record == null) {
                throw new IllegalStateException("No record found for strategy type: " + currentStrategyType);
            }
            currentStrategy = strategyManager.createStrategy(series, currentStrategyType, record.parameters());
        }
        return currentStrategy;
    }
    
    @Override
    public void updateRecord(StrategyType type, Any parameters, double score) {
        strategyRecords.put(type, new StrategyRecord(type, parameters, score));
    }
    
    @Override
    public StrategyState selectBestStrategy(BarSeries series) {
        if (strategyRecords.isEmpty()) {
            throw new IllegalStateException("No optimized strategy found");
        }
        
        StrategyRecord bestRecord = strategyRecords.values().stream()
            .max((r1, r2) -> Double.compare(r1.score(), r2.score()))
            .orElseThrow(() -> new IllegalStateException("No optimized strategy found"));
            
        this.currentStrategyType = bestRecord.strategyType();
        this.currentStrategy = null;  // Force re-creation of strategy with new parameters
        
        try {
            this.currentStrategy = strategyManager.createStrategy(series, currentStrategyType, bestRecord.parameters());
        } catch (Exception e) {
            throw new RuntimeException("Failed to create strategy", e);
        }
        return this;
    }
    
    @Override
    public Strategy toStrategyMessage() {
        StrategyRecord record = strategyRecords.get(currentStrategyType);
        if (record == null) {
            throw new IllegalStateException("No record found for current strategy type: " + currentStrategyType);
        }
        
        return Strategy.newBuilder()
                .setType(currentStrategyType)
                .setParameters(record.parameters())
                .build();
    }
    
    @Override
    public Iterable<StrategyType> getStrategyTypes() {
        return strategyRecords.keySet();
    }
    
    @Override
    public StrategyType getCurrentStrategyType() {
        return currentStrategyType;
    }
}
