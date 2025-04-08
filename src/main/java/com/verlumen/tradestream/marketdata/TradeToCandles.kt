package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SimpleFunction
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import java.util.function.Supplier

/**
 * Transforms a stream of trades into OHLCV candles.
 * Uses a stateful DoFn with timers to ensure candles are produced
 * for all tracked currency pairs, even when no trades occur.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val windowDuration: Duration,
    @Assisted private val defaultPrice: Double,
    private val currencyPairsSupplier: Supplier<List<CurrencyPair>>,
    private val candleCreatorFnFactory: CandleCreatorFn.Factory
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>() {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    interface Factory {
        fun create(windowDuration: Duration, defaultPrice: Double): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log("Starting TradeToCandle transform with window duration: %s", windowDuration)

        // Key trades by currency pair
        val keyedTrades = input.apply("KeyByCurrencyPair", 
            MapElements.via(object : SimpleFunction<Trade, KV<String, Trade>>() {
                override fun apply(trade: Trade): KV<String, Trade> {
                    logger.atFine().log("Keying trade: %s by pair: %s", 
                        trade.tradeId, trade.currencyPair)
                    return KV.of(trade.currencyPair, trade)
                }
            }))

        // Apply fixed windows
        val windowedTrades = keyedTrades.apply("FixedWindows", 
            Window.into(FixedWindows.of(windowDuration)))

        // Process into candles with defaults for missing data
        return windowedTrades.apply("CreateCandles", 
            ParDo.of(candleCreatorFnFactory.create(windowDuration, defaultPrice)))
    }
}
