package com.verlumen.tradestream.strategies;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicReference;
import org.ta4j.core.BarSeries;

final class StrategyStateFactoryImpl implements StrategyState.Factory {
    private static final StrategyType DEFAULT_STRATEGY_TYPE = StrategyType.SMA_RSI;

    private final StrategyManager strategyManager;

    @Inject
    StrategyStateFactoryImpl(StrategyManager strategyManager) {
        this.strategyManager = strategyManager;
    }

    @Override
    public StrategyState create() {
        return StrategyStateImpl.create(strategyManager);
    }

    /**
     * Implementation of the {@link StrategyState} interface.
     * This class is serializable to support Beam state APIs.
     */
    private static record StrategyStateImpl(
        StrategyManager strategyManager,
        Map<StrategyType, StrategyRecord> strategyRecords,
        AtomicReference<StrategyType> currentStrategyType
    ) implements StrategyState {

        private static StrategyStateImpl create(StrategyManager strategyManager) {
            Map<StrategyType, StrategyRecord> strategyRecords = new ConcurrentHashMap<>();
            for (StrategyType type : strategyManager.getStrategyTypes()) {
                strategyRecords.put(
                    type,
                    StrategyRecord.create(
                        type,
                        strategyManager.getDefaultParameters(type)
                    )
                );
            }
            return new StrategyStateImpl(
                strategyManager, 
                strategyRecords, 
                new AtomicReference<>(DEFAULT_STRATEGY_TYPE)
            );
        }

        @Override
        public org.ta4j.core.Strategy getCurrentStrategy(BarSeries series)
                throws InvalidProtocolBufferException {           
            StrategyRecord record = strategyRecords.get(currentStrategyType.get());
            return strategyManager.createStrategy(
                series, 
                currentStrategyType.get(), 
                record.parameters()
            );
        }

        @Override
        public void updateRecord(StrategyType type, Any parameters, double score) {
            strategyRecords.put(type, StrategyRecord.create(type, parameters, score));
        }

        @Override
        public StrategyState selectBestStrategy(BarSeries series) {
            StrategyRecord bestRecord = strategyRecords.values().stream()
                .max((r1, r2) -> Double.compare(r1.score(), r2.score()))
                .orElseThrow(() -> new IllegalStateException("No optimized strategy found"));
            
            currentStrategyType.set(bestRecord.strategyType());
            
            return this;
        }

        @Override
        public Strategy toStrategyMessage() {
            StrategyRecord record = strategyRecords.get(currentStrategyType.get());
            return Strategy.newBuilder()
                    .setType(currentStrategyType.get())
                    .setParameters(record.parameters())
                    .build();
        }

        @Override
        public Iterable<StrategyType> getStrategyTypes() {
            return strategyRecords.keySet();
        }

        @Override
        public StrategyType getCurrentStrategyType() {
            return currentStrategyType.get();
        }
    }
}
