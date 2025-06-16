package com.verlumen.tradestream.strategies

object StrategyConstants {
    @JvmField
    val supportedStrategyTypes: Set<StrategyType> =
        setOf(
            StrategyType.EMA_MACD,
        )
}
