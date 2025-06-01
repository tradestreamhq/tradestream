package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.protobuf.Timestamp

// Assuming Candle class/proto is defined elsewhere in your project or this package.
// If Candle is in a different package, you might need an import for it here too,
// though it's only used as a return type in the interface.
// import com.verlumen.tradestream.proto.Candle // Example if Candle is a proto

/**
 * Interface for fetching candle data.
 */
interface CandleFetcher : AutoCloseable {
    /**
     * Fetches candle data for a given symbol within a specified time range.
     *
     * @param symbol The trading symbol (e.g., "BTC-USD").
     * @param startTime The start of the time range (inclusive).
     * @param endTime The end of the time range (exclusive or inclusive based on the underlying data source's query behavior).
     * @return An immutable list of [Candle] objects.
     */
    fun fetchCandles(
        symbol: String,
        startTime: Timestamp,
        endTime: Timestamp,
    ): ImmutableList<Candle>

    // The close() method is implicitly required by extending AutoCloseable
    // and must be implemented by concrete classes.
    override fun close() // It's good practice to declare it in the interface if it extends AutoCloseable
}
