package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.momentumoscillators.MomentumOscillatorParams;
import com.verlumen.tradestream.backtesting.trendfollowing.TrendFollowingParams;

final class ParamConfigs {
    static final ImmutableList<ParamConfig> ALL_CONFIGS = 
        ImmutableList.<ParamConfig>builder()
            .addAll(MomentumOscillatorParams.ALL_CONFIGS)
            .addAll(TrendFollowingParams.allConfigs)
            .build();

    // Prevent instantiation
    private ParamConfigs() {}
}
