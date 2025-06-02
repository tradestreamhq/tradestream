package com.verlumen.tradestream.backtesting.trendfollowing

import com.verlumen.tradestream.discovery.ParamConfig

object TrendFollowingParams {
    @JvmField
    val allConfigs: List<ParamConfig> =
        listOf(
            IchimokuCloudParamConfig.create(),
        )
}
