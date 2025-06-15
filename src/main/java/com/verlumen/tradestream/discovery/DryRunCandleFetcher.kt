package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.marketdata.CandleFetcher
import java.io.Serializable

/** Simple serialisable [CandleFetcher] for dry runs. */
internal class DryRunCandleFetcher : CandleFetcher, Serializable {
    override fun fetchCandles(
        symbol: String,
        startTime: Timestamp,
        endTime: Timestamp,
    ): ImmutableList<Candle> = ImmutableList.of(createDummyCandle(symbol, startTime))

    private fun createDummyCandle(
        symbol: String,
        ts: Timestamp,
    ): Candle =
        Candle
            .newBuilder()
            .setTimestamp(ts)
            .setCurrencyPair(symbol)
            .setOpen(100.0)
            .setHigh(110.0)
            .setLow(90.0)
            .setClose(105.0)
            .setVolume(1_000.0)
            .build()

    companion object {
        private const val serialVersionUID = 1L
    }
}
