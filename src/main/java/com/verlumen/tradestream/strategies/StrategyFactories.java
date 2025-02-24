package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.strategies.movingaverages.MovingAverageStrategies;
import com.verlumen.tradestream.strategies.oscillators.OscillatorStrategies;

/**
 * Provides a centralized collection of all available strategy factories across all categories.
 * This class aggregates factories from child packages (moving averages, oscillators, etc.)
 * and is immutable and thread-safe.
 */
public final class StrategyFactories {
    /**
     * An immutable list of all strategy factories across all categories.
     */
    public static final ImmutableList<StrategyFactory<?>> ALL_FACTORIES = 
        ImmutableList.<StrategyFactory<?>>builder()
            .addAll(MovingAverageStrategies.ALL_FACTORIES)
            .addAll(OscillatorStrategies.ALL_FACTORIES)
            .build();

    // Prevent instantiation
    private StrategyFactories() {}
}
