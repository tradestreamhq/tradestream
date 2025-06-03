package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.StrategyType

/**
 * Represents the parameters required to produce a fitness function.
 *
 * @property strategyType The type of trading strategy to be evaluated.
 * @property candles A list of historical market data candles.
 */
data class FitnessFunctionParams(
    val strategyType: StrategyType,
    val candles: List<Candle>,
)
