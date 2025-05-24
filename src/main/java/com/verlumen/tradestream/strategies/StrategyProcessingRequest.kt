package com.verlumen.tradestream.strategies

import com.verlumen.tradestream.marketdata.Candle
import java.io.Serializable

/**
 * Helper class representing a request to process a single strategy type.
 */
internal data class StrategyProcessingRequest(
    val strategyType: StrategyType,
    val candles: List<Candle>,
) : Serializable
