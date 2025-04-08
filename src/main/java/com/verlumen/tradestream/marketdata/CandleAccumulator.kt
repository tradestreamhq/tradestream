package com.verlumen.tradestream.marketdata

import java.io.Serializable

/**
 * Class to hold the intermediate candle data for aggregation.
 */
class CandleAccumulator : Serializable {
    var initialized: Boolean = false
    var open: Double = 0.0
    var high: Double = 0.0
    var low: Double = Double.MAX_VALUE
    var close: Double = 0.0
    var volume: Double = 0.0
    var timestamp: Long = 0
    var currencyPair: String = ""
    var isDefault: Boolean = true
    
    companion object {
        private const val serialVersionUID = 1L
    }
    
    override fun toString(): String {
        return "CandleAccumulator{initialized=$initialized, open=$open, high=$high, " +
            "low=$low, close=$close, volume=$volume, currencyPair='$currencyPair', isDefault=$isDefault}"
    }
}
