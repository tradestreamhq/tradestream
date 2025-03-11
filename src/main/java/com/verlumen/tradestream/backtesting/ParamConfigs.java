package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.oscillators.OscillatorStrategies;

public final class ParamConfigs {
    public static final ImmutableList<ParamConfig> ALL_CONFIGS = 
        ImmutableList.<ParamConfig<?>>builder()
            .addAll(OscillatorParams.ALL_CONFIGS)
            .build();

    // Prevent instantiation
    private ParamConfigs() {}
}
