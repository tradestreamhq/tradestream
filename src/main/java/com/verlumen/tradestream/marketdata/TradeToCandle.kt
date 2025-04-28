package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.*
import org.joda.time.Duration
import java.io.Serializable
import com.google.protobuf.Timestamp // Ensure correct Timestamp import

/**
 * Transforms a stream of trades into OHLCV candles using Combine.perKey.
 * This version ONLY produces candles for windows containing actual trades.
 * Fill-forward logic needs to be handled by a separate downstream transform.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val windowDuration: Duration,
    // CandleCombineFn needs to be injectable or accessible
    // Assuming SlidingCandleAggregator.CandleCombineFn is accessible/injectable
    private val candleCombineFn: SlidingCandleAggregator.CandleCombineFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 3L // Use version 3 for this implementation
    }

    // Factory remains the same
    interface Factory {
        fun create(windowDuration: Duration): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log("Starting TradeToCandle transform (Combine.perKey version) with window duration: %s", windowDuration)

        // Key trades by currency pair
        val keyedTrades: PCollection<KV<String, Trade>> = input.apply("KeyByCurrencyPair",
            MapElements.into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Trade::class.java)))
                .via(SerializableFunction<Trade, KV<String, Trade>> { trade ->
                    KV.of(trade.currencyPair, trade)
                })
        ).setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade::class.java))) // Ensure coder is set

        // Apply windowing
        val windowedTrades: PCollection<KV<String, Trade>> = keyedTrades.apply("WindowTrades",
            Window.into<KV<String, Trade>>(FixedWindows.of(windowDuration))
        )

        // Aggregate trades into Candles per key using Combine.perKey
        val candles: PCollection<KV<String, Candle>> = windowedTrades.apply("AggregateToCandle",
            Combine.perKey(candleCombineFn) // Use the injected CandleCombineFn
        ).setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java))) // Ensure coder is set

        return candles.setName("AggregatedCandles")
    }
}
