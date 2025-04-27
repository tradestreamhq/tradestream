package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.*
import org.joda.time.Duration
import java.io.Serializable

/**
 * Transforms a stream of trades into OHLCV candles using stateful aggregation.
 * When no trades occur in a window, it uses the previous candle's close price
 * to create a continuation candle with zero volume. If no previous candle exists,
 * no candle will be produced.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val windowDuration: Duration,
    private val candleCreatorFn: CandleCreatorFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L
    }

    interface Factory {
        fun create(windowDuration: Duration): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log("Starting TradeToCandle transform with window duration: %s", windowDuration)

        // Key trades by currency pair
        val keyedTrades = input.apply("KeyByCurrencyPair",
            MapElements.into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Trade::class.java)))
                .via(SerializableFunction<Trade, KV<String, Trade>> { trade -> KV.of(trade.currencyPair, trade) })
        )

        // Apply windowing
        val windowedTrades = keyedTrades.apply("WindowTrades",
            Window.into<KV<String, Trade>>(FixedWindows.of(windowDuration))
        )

        // Process with stateful DoFn that handles both actual candles and fill-forward logic
        val candles = windowedTrades
            .apply("AggregateAndFillForwardCandles", ParDo.of(candleCreatorFn))
            .setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))

        return candles.setName("CandlesWithFillForward")
    }
}
