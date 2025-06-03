package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.strategies.StrategyType
import com.verlumen.tradestream.marketdata.Candle

/**
 * Represents the parameters required for a fitness calculation.
 *
 * @property strategyType The type of trading strategy to be evaluated.
 * @property candles A list of historical market data candles.
 */
data class FitnessCalculationParams(
    val strategyType: StrategyType,
    val candles: List<Candle>
)
