package com.verlumen.tradestream.marketdata

import java.io.Serializable

/**
 * Class to hold the intermediate candle data for aggregation.
 */
class CandleAccumulator : Serializable {
    var currencyPair: String = ""
    var open: Double = 0.0
    var high: Double = 0.0
    var low: Double = 0.0
    var close: Double = 0.0
    var volume: Double = 0.0
    var timestamp: Long = 0 // Used for candle timestamp in final output
    var initialized: Boolean = false
    var isDefault: Boolean = false
    var firstTradeTimestamp: Long = Long.MAX_VALUE // Track earliest trade timestamp
    var latestTradeTimestamp: Long = Long.MIN_VALUE // Track latest trade timestamp for close price

    companion object {
        private const val serialVersionUID = 1L
    }

    override fun toString(): String {
        return "CandleAccumulator{initialized=$initialized, open=$open, high=$high, " +
                "low=$low, close=$close, volume=$volume, currencyPair='$currencyPair', isDefault=$isDefault}"
    }
}
