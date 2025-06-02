package com.verlumen.tradestream.backtesting.movingaverages

import com.verlumen.tradestream.discovery.ParamConfig

object MovingAverageParams {
    @JvmField
    val allConfigs: List<ParamConfig> =
        listOf(
            EmaMacdParamConfig.create(),
        )
}
