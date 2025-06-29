package com.verlumen.tradestream.marketdata

import com.google.protobuf.Timestamp

/**
 * Interface for fetching candle data.
 */
interface CandleFetcher {
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
    ): List<Candle>
}
