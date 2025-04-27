package com.verlumen.tradestream.marketdata

import java.io.Serializable

/**
 * Accumulator for building a Candle within a single window.
 * Used by stateful DoFn [CandleCreatorFn].
 */
class CandleAccumulator : Serializable {
    var currencyPair: String = ""
    var open: Double = 0.0
    var high: Double = Double.MIN_VALUE
    var low: Double = Double.MAX_VALUE
    var close: Double = 0.0
    var volume: Double = 0.0
    var timestamp: Long = 0 // Used for candle timestamp (first trade time) in final output
    var initialized: Boolean = false
    var firstTradeTimestamp: Long = Long.MAX_VALUE // Track earliest trade timestamp for open price and candle timestamp
    var latestTradeTimestamp: Long = Long.MIN_VALUE // Track latest trade timestamp for close price

    companion object {
        private const val serialVersionUID = 1L
    }

    override fun toString(): String {
        return "CandleAccumulator{initialized=$initialized, open=$open, high=$high, " +
                "low=$low, close=$close, volume=$volume, currencyPair='$currencyPair'}"
    }
}
