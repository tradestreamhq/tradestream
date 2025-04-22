package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.timestamp
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.coders.SerializableCoder
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
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.Serializable
import java.util.function.Supplier

/**
 * Stateful DoFn that creates candles from trades, with default candles
 * for currency pairs that don't have trades in a given window.
 */
class CandleCreatorFn @Inject constructor(
    @Assisted private val windowDuration: Duration,
    @Assisted private val defaultPrice: Double,
    private val currencyPairsSupplier: Supplier<List<CurrencyPair>>
) : DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {
    
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L
    }
    
    interface Factory {
        fun create(windowDuration: Duration, defaultPrice: Double): CandleCreatorFn
    }
    
    @StateId("activeCurrencyPairs")
    private val activePairsSpec: StateSpec<ValueState<MutableSet<String>>> = 
        StateSpecs.value(SetCoder.of(org.apache.beam.sdk.coders.StringUtf8Coder.of()))
    
    @StateId("currentCandle")
    private val currentCandleSpec: StateSpec<ValueState<CandleAccumulator>> =
        StateSpecs.value(SerializableCoder.of(CandleAccumulator::class.java))
    
    @TimerId("endOfWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)
    
    @Setup
    fun setup() {
        logger.atInfo().log("Setting up CandleCreatorFn with window duration: %s", windowDuration)
    }
    
    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Trade>,
        @StateId("activeCurrencyPairs") activePairsState: ValueState<MutableSet<String>>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @TimerId("endOfWindowTimer") timer: Timer,
        window: BoundedWindow
    ) {
        val currencyPair = element.key
        val trade = element.value
        
        logger.atFine().log("Processing trade for %s: %s", currencyPair, trade.tradeId)
        
        // Track active currency pairs
        trackActiveCurrencyPair(currencyPair, activePairsState)
        
        // Set window end timer for all currency pairs
        timer.set(window.maxTimestamp())
        
        // Process the trade into our candle accumulator
        processTradeIntoCandle(currencyPair, trade, currentCandleState)
    }
    
    private fun trackActiveCurrencyPair(
        currencyPair: String,
        activePairsState: ValueState<MutableSet<String>>
    ) {
        var activePairs = activePairsState.read()
        if (activePairs == null) {
            activePairs = mutableSetOf()
        }
        
        if (!activePairs.contains(currencyPair)) {
            logger.atFine().log("Adding %s to active currency pairs", currencyPair)
            activePairs.add(currencyPair)
            activePairsState.write(activePairs)
        }
    }
    
    private fun processTradeIntoCandle(
        currencyPair: String,
        trade: Trade,
        currentCandleState: ValueState<CandleAccumulator>
    ) {
        var accumulator = currentCandleState.read()
        if (accumulator == null) {
            accumulator = CandleAccumulator()
            accumulator.currencyPair = currencyPair
            accumulator.timestamp = trade.timestamp.seconds
            
            logger.atFine().log("Created new accumulator for %s", currencyPair)
        }
        
        // Skip default trades if we already have real trades
        if (trade.exchange == "DEFAULT" && !accumulator.isDefault) {
            logger.atFine().log("Skipping default trade - already have real trades")
            return
        }
        
        if (!accumulator.initialized) {
            // Initialize with first trade
            accumulator.initialized = true
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.isDefault = trade.exchange == "DEFAULT"
            
            logger.atFine().log("Initialized accumulator with %s trade", 
                if (accumulator.isDefault) "DEFAULT" else "real")
        } else if (trade.exchange != "DEFAULT") {
            // Update with real trade
            accumulator.high = maxOf(accumulator.high, trade.price)
            accumulator.low = minOf(accumulator.low, trade.price)
            accumulator.close = trade.price
            accumulator.volume += trade.volume
            accumulator.isDefault = false
            
            logger.atFine().log("Updated accumulator with real trade, price: %.2f", trade.price)
        }
        
        currentCandleState.write(accumulator)
    }
    
    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("activeCurrencyPairs") activePairsState: ValueState<MutableSet<String>>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>
    ) {
        val activePairs = activePairsState.read() ?: mutableSetOf()
        val currentWindowTime = context.timestamp()
        logger.atInfo().log("Window timer fired at %s for %d active pairs", 
            currentWindowTime, activePairs.size)
        
        // Output accumulated candle for the active currency pair
        val accumulator = currentCandleState.read()
        if (accumulator != null && accumulator.initialized) {
            val candle = buildCandleFromAccumulator(accumulator)
            context.output(KV.of(accumulator.currencyPair, candle))
            logger.atFine().log("Output candle for %s: %s", 
                accumulator.currencyPair, candleToString(candle))
        }
        
        // Also check all known currency pairs and output default candles as needed
        for (pair in currencyPairsSupplier.get()) {
            val symbol = pair.symbol()
            if (!activePairs.contains(symbol)) {
                // Create default candle for inactive pair
                val defaultCandle = createDefaultCandle(symbol, currentWindowTime)
                context.output(KV.of(symbol, defaultCandle))
                logger.atFine().log("Output default candle for inactive pair %s", symbol)
            }
        }
        
        // Clear state for next window
        currentCandleState.clear()
        activePairsState.clear()
    }
    
    private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
        val builder = Candle.newBuilder()
            .setOpen(acc.open)
            .setHigh(acc.high)
            .setLow(acc.low)
            .setClose(acc.close)
            .setVolume(acc.volume)
            .setCurrencyPair(acc.currencyPair)
        
        builder.setTimestamp(timestamp {
            seconds = acc.timestamp
        })
        
        return builder.build()
    }
    
    private fun createDefaultCandle(currencyPair: String, windowTime: Instant): Candle {
        logger.atFine().log("Creating default candle for %s at %s", currencyPair, windowTime)
        
        val builder = Candle.newBuilder()
            .setOpen(defaultPrice)
            .setHigh(defaultPrice)
            .setLow(defaultPrice)
            .setClose(defaultPrice)
            .setVolume(0.0)
            .setCurrencyPair(currencyPair)
        
        builder.setTimestamp(timestamp {
            seconds = windowTime.getMillis() / 1000
        })
        
        return builder.build()
    }
    
    private fun candleToString(candle: Candle): String {
        return "Candle{O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
    }
}
