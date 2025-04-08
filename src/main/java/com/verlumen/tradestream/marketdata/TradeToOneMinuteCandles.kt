package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.instruments.CurrencyPair
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.marketdata.Trade
import org.apache.beam.sdk.coders.SetCoder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SimpleFunction
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.joda.time.Instant
import java.util.function.Supplier

/**
 * Transforms a stream of trades into one-minute OHLCV candles.
 * Uses a stateful DoFn with timers to ensure candles are produced
 * for all tracked currency pairs, even when no trades occur.
 */
class TradeToOneMinuteCandles(
    private val currencyPairsSupplier: Supplier<List<CurrencyPair>>,
    private val defaultPrice: Double
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>() {
    
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val ONE_MINUTE = Duration.standardMinutes(1)
    }
    
    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log("Starting TradeToOneMinuteCandles transform")
        
        // Key trades by currency pair
        val keyedTrades = input.apply("KeyByCurrencyPair", 
            MapElements.via(object : SimpleFunction<Trade, KV<String, Trade>>() {
                override fun apply(trade: Trade): KV<String, Trade> {
                    logger.atFine().log("Keying trade: %s by pair: %s", 
                        trade.tradeId, trade.currencyPair)
                    return KV.of(trade.currencyPair, trade)
                }
            }))
        
        // Apply fixed 1-minute windows
        val windowedTrades = keyedTrades.apply("FixedOneMinuteWindows", 
            Window.into(FixedWindows.of(ONE_MINUTE)))
        
        // Process into candles with defaults for missing data
        return windowedTrades.apply("CreateCandles", 
            ParDo.of(CandleCreatorFn(currencyPairsSupplier, defaultPrice)))
    }
}
