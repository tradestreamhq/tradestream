package com.verlumen.tradestream.backtesting.oscillators;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.ParamConfig;

/**
 * Provides a centralized collection of all available oscillator-based param configs.
 * This class is immutable and thread-safe. As more oscillator strategies are added,
 * they should be included in ALL_CONFIGS.
 */
public final class OscillatorParams {
    /**
     * An immutable list of all oscillator param configs.
     */
    public static final ImmutableList<ParamConfig<?>> ALL_CONFIGS = ImmutableList.of(
        SmaRsiParamConfig.create()
    );

    // Prevent instantiation
    private OscillatorParams() {}
}
