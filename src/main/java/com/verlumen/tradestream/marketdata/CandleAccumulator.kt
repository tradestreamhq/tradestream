package com.verlumen.tradestream.marketdata

import com.verlumen.tradestream.protos.marketdata.Candle
import com.google.protobuf.Timestamp
import java.io.Serializable
import org.joda.time.Instant

/**
 * Accumulator for creating OHLCV candles.
 * Mutable state used within a Beam DoFn.
 */
class CandleAccumulator : Serializable {
    var open: Double = 0.0
    var high: Double = Double.MIN_VALUE
    var low: Double = Double.MAX_VALUE
    var close: Double = 0.0
    lateinit var currencyPair: String
    var volume: Double = 0.0
    var timestamp: Long = 0 // Used for candle timestamp in final output
    var initialized: Boolean = false
    var firstTradeTimestamp: Long = Long.MAX_VALUE // Track earliest trade timestamp
    var latestTradeTimestamp: Long = Long.MIN_VALUE // Track latest trade timestamp for close price

    companion object {
        private const val serialVersionUID = 1L
    }

    override fun toString(): String {
        return "CandleAccumulator{initialized=$initialized, open=$open, high=$high, " +
                "low=$low, close=$close, volume=$volume, currencyPair='$currencyPair'}"
    }
}
