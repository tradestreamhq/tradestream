package com.verlumen.tradestream.strategies;

import com.google.inject.assistedinject.Assisted;
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
    private final StrategyManager strategyManager;
    private final Map<StrategyType, StrategyRecord> strategyRecords;
    private StrategyType currentStrategyType;
    private transient org.ta4j.core.Strategy currentStrategy;
    
    @Inject
    StrategyStateImpl(
        StrategyManager strategyManager,
        @Assisted Map<StrategyType, StrategyRecord> strategyRecords,
        @Assisted StrategyType currentStrategyType) {
        this.strategyManager = strategyManager;
        this.strategyRecords = strategyRecords;
        this.currentStrategyType = currentStrategyType;
    }
    
    @Override
    public org.ta4j.core.Strategy getCurrentStrategy(BarSeries series)
            throws InvalidProtocolBufferException {
        if (currentStrategy == null) {
            StrategyRecord record = strategyRecords.get(currentStrategyType);
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
        StrategyRecord bestRecord = strategyRecords.values().stream()
            .max((r1, r2) -> Double.compare(r1.score(), r2.score()))
            .orElseThrow(() -> new IllegalStateException("No optimized strategy found"));
        this.currentStrategyType = bestRecord.strategyType();
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
