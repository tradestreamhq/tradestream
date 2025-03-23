package com.verlumen.tradestream.strategies;

import com.verlumen.tradestream.marketdata.Candle;

/**
 * Helper class representing a request to process a single strategy type.
 */
internal data class StrategyProcessingRequest(
    val strategyType: StrategyType, 
    val candles: List<Candle>
) : Serializable
