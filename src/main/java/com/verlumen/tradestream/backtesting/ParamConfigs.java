package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.momentumoscillators.MomentumOscillatorParams;
import com.verlumen.tradestream.backtesting.movingaverages.MovingAverageParams;
import com.verlumen.tradestream.backtesting.patternrecognition.PatternRecognitionParams;

final class ParamConfigs {
    static final ImmutableList<ParamConfig> ALL_CONFIGS = 
        ImmutableList.<ParamConfig>builder()
            .addAll(MomentumOscillatorParams.allConfigs)
            .addAll(MovingAverageParams.allConfigs)
            .addAll(PatternRecognitionParams.allConfigs)
            .build();

    // Prevent instantiation
    private ParamConfigs() {}
}
