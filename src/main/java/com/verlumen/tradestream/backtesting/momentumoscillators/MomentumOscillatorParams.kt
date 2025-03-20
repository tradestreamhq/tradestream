package com.verlumen.tradestream.backtesting.momentumoscillators

import com.verlumen.tradestream.backtesting.ParamConfig

/**
 * Provides a centralized collection of all available oscillator-based param configs.
 * This class is immutable and thread-safe. As more oscillator strategies are added,
 * they should be included in ALL_CONFIGS.
 */
object MomentumOscillatorParams {
    public val ALL_CONFIGS: List<ParamConfig> = listOf(
        AdxStochasticParamConfig.create(),
        SmaRsiParamConfig.create()
    )
}
