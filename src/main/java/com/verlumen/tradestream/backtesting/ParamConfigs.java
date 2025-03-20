package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.momentumoscillators.MomentumOscillatorParams;

final class ParamConfigs {
    static final ImmutableList<ParamConfig> ALL_CONFIGS = 
        ImmutableList.<ParamConfig>builder()
            .addAll(MomentumOscillatorParams.allConfigs)
            .build();

    // Prevent instantiation
    private ParamConfigs() {}
}
