package com.verlumen.tradestream.strategies;

object StrategyConstants {
    @JvmField
    val supportedStrategyTypes: Set<StrategyType> = setOf(
        StrategyType.SMA_RSI,
        StrategyType.EMA_MACD,
        StrategyType.ADX_STOCHASTIC
    );
}
