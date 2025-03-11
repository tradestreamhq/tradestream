package com.verlumen.tradestream.strategies.oscillators;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.strategies.StrategyFactory;

/**
 * Provides a centralized collection of all available oscillator-based strategy factories.
 * This class is immutable and thread-safe. As more oscillator strategies are added,
 * they should be included in ALL_FACTORIES.
 */
public final class OscillatorStrategies {
    /**
     * An immutable list of all oscillator strategy factories.
     */
    public static final ImmutableList<StrategyFactory<?>> ALL_FACTORIES = ImmutableList.builder()
        .add(AdxStochasticStrategyFactory.create())
        .add(SmaRsiStrategyFactory.create())
        .build();

    // Prevent instantiation
    private OscillatorStrategies() {}
}
