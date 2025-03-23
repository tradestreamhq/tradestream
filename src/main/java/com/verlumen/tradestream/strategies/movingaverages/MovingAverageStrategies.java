package com.verlumen.tradestream.strategies.movingaverages;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.strategies.StrategyFactory;

/**
 * Provides a centralized collection of all available moving average-based strategy factories.
 * This class is immutable and thread-safe.
 */
public final class MovingAverageStrategies {
    /**
     * An immutable list of all moving average strategy factories.
     */
    public static final ImmutableList<StrategyFactory<?>> ALL_FACTORIES = ImmutableList.of(
        DoubleEmaCrossoverStrategyFactory.create(),
        MomentumSmaCrossoverStrategyFactory.create(),
        EmaMacdStrategyFactory.create(),
        SmaEmaCrossoverStrategyFactory.create(),
        TripleEmaCrossoverStrategyFactory.create()
    );

    // Prevent instantiation
    private MovingAverageStrategies() {}
}
