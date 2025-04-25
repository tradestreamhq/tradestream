package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.SetCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
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
import org.apache.beam.sdk.transforms.windowing.IntervalWindow // Import IntervalWindow
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
        StateSpecs.value(SetCoder.of(StringUtf8Coder.of()))

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

        logger.atFine().log("Processing trade for %s: %s in window %s", currencyPair, trade.tradeId, window)

        // Track active currency pairs
        trackActiveCurrencyPair(currencyPair, activePairsState)

        // Set window end timer for all currency pairs *relative to the window*
        timer.set(window.maxTimestamp())
        logger.atFine().log("Setting timer for key %s to window max timestamp: %s", currencyPair, window.maxTimestamp())

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
            // Store timestamp (seconds) of the *first* trade seen for this candle
            accumulator.timestamp = trade.timestamp.seconds

            logger.atFine().log("Created new accumulator for %s with first trade timestamp %d",
                 currencyPair, accumulator.timestamp)
        }

        // Skip default trades if we already have real trades
        if (trade.exchange == "DEFAULT" && !accumulator.isDefault) {
            logger.atFine().log("Skipping default trade - already have real trades")
            return
        }

        if (!accumulator.initialized) {
            // Initialize with first trade (or default trade)
            accumulator.initialized = true
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.isDefault = trade.exchange == "DEFAULT"

            logger.atFine().log("Initialized accumulator with %s trade (Price: %.2f, Volume: %.2f)",
                if (accumulator.isDefault) "DEFAULT" else "real", trade.price, trade.volume)
        } else if (trade.exchange != "DEFAULT") {
            // Update with real trade (overwriting default if needed)
             if (accumulator.isDefault) {
                 // First real trade overwrites default completely
                 logger.atFine().log("Overwriting default accumulator with first real trade for %s", currencyPair)
                 accumulator.open = trade.price
                 accumulator.high = trade.price
                 accumulator.low = trade.price
                 accumulator.close = trade.price
                 accumulator.volume = trade.volume
                 accumulator.isDefault = false
                 // Update timestamp to first *real* trade
                 accumulator.timestamp = trade.timestamp.seconds
             } else {
                 // Subsequent real trade updates normally
                 accumulator.high = maxOf(accumulator.high, trade.price)
                 accumulator.low = minOf(accumulator.low, trade.price)
                 accumulator.close = trade.price
                 accumulator.volume += trade.volume
                 // isDefault remains false
             }
            logger.atFine().log("Updated accumulator with real trade, price: %.2f", trade.price)
        }
        // If initialized and trade is DEFAULT, do nothing further

        currentCandleState.write(accumulator)
    }

    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("activeCurrencyPairs") activePairsState: ValueState<MutableSet<String>>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        window: BoundedWindow // Get window information
    ) {
        val activePairs = activePairsState.read() ?: mutableSetOf()
        val currentKey = context.key() // Get the key for which the timer fired
        val accumulator = currentCandleState.read() // Read state for the current key

        // Use window.maxTimestamp() as the definitive time for this timer firing
        val windowEndTime = window.maxTimestamp()

        logger.atInfo().log(
            "Window timer fired for key '%s'. Context timestamp: %s, WindowEnd: %s. Active pairs in state: %d.",
            currentKey, context.timestamp(), windowEndTime, activePairs.size
        )

        // Output accumulated candle for the *current key* if it exists and was initialized
        if (accumulator != null && accumulator.initialized) {
            val candle = buildCandleFromAccumulator(accumulator)
            // Output with timestamp matching the *first trade* seen in the window
            context.outputWithTimestamp(KV.of(accumulator.currencyPair, candle), Instant(accumulator.timestamp * 1000))
            logger.atFine().log("Output actual candle for %s: %s with event time %d",
                accumulator.currencyPair, candleToString(candle), accumulator.timestamp)
        } else {
             logger.atInfo().log("No initialized accumulator found for key '%s' at window end.", currentKey)
        }

        // Check all known currency pairs and output default candles *if this key matches*
        // This prevents duplicate default generation if multiple keys fire timers
        // A more robust design might involve a downstream step, but this works for basic cases.
        val allKnownPairs = currencyPairsSupplier.get()
        val currentPairSymbol = currentKey // Assuming key is the currency pair symbol

        if (allKnownPairs.any { it.symbol() == currentPairSymbol }) {
            if (!activePairs.contains(currentPairSymbol)) {
                 // If the timer fired for a key that ended up having no *initialized* accumulator (e.g., only default trades skipped)
                 // OR more likely, if a timer fires for a key that never received *any* elements in the window (depends on runner behavior)
                 // We should still generate a default candle for this key if it's in the known list.
                 logger.atInfo().log("Generating default candle for key '%s' as it was not marked active.", currentPairSymbol)
                 try {
                     val defaultCandle = createDefaultCandle(currentPairSymbol, windowEndTime)
                     // Output default candle using the window end time
                     context.outputWithTimestamp(KV.of(currentPairSymbol, defaultCandle), windowEndTime)
                     logger.atFine().log("Output default candle for inactive pair %s at window end %s", currentPairSymbol, windowEndTime)
                 } catch (e: IllegalStateException) {
                     logger.atSevere().withCause(e).log("Failed to generate default candle for %s", currentPairSymbol)
                 }
            }
        } else {
             logger.atWarning().log("Timer fired for key '%s' which is not in the known currency pair list.", currentKey)
        }


        // Simplified logic (Original): Generate defaults for ALL inactive pairs here.
        // This can lead to duplicates if multiple timers fire near-simultaneously in distributed runners.
        // Keep the improved logic above.
        /*
        for (pair in currencyPairsSupplier.get()) {
            val symbol = pair.symbol()
            if (!activePairs.contains(symbol)) {
                // Create default candle for inactive pair
                try {
                    val defaultCandle = createDefaultCandle(symbol, windowEndTime)
                    // Output default candle using the window end time
                    context.outputWithTimestamp(KV.of(symbol, defaultCandle), windowEndTime)
                    logger.atFine().log("Output default candle for inactive pair %s at window end %s", symbol, windowEndTime)
                } catch (e: IllegalStateException) {
                     logger.atSevere().withCause(e).log("Failed to generate default candle for %s", symbol)
                }
            }
        }
        */

        // Clear state for the *current key* for the next window
        currentCandleState.clear()
        activePairsState.clear() // Clears the set for this key
        logger.atFine().log("Cleared state for key '%s'", currentKey)
    }

    private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
        val builder = Candle.newBuilder()
            .setOpen(acc.open)
            .setHigh(acc.high)
            .setLow(acc.low)
            .setClose(acc.close)
            .setVolume(acc.volume)
            .setCurrencyPair(acc.currencyPair)

        // Timestamp represents the first trade's timestamp (in seconds)
        builder.setTimestamp(Timestamps.fromSeconds(acc.timestamp))

        return builder.build()
    }

    private fun createDefaultCandle(currencyPair: String, windowEnd: Instant): Candle {
        logger.atFine().log("Creating default candle for %s at window end %s", currencyPair, windowEnd)

        // Check if the timestamp is valid before creating the Candle proto
        if (windowEnd.millis == Long.MIN_VALUE || windowEnd.millis == Long.MAX_VALUE ) {
             logger.atSevere().log("Cannot create default candle for %s, windowEnd timestamp is invalid: %s", currencyPair, windowEnd)
             // Throw exception to signal failure clearly
             throw IllegalStateException("Default candle generation failed due to invalid timestamp ($windowEnd) for pair $currencyPair")
        }
        val protoTimestamp = try {
             Timestamps.fromMillis(windowEnd.millis)
        } catch (e: IllegalArgumentException) {
             logger.atSevere().withCause(e).log("Failed to convert windowEnd Instant %s (millis: %d) to Protobuf Timestamp for %s",
                 windowEnd, windowEnd.millis, currencyPair)
             throw IllegalStateException("Timestamp conversion failed for default candle $currencyPair", e)
        }


        val builder = Candle.newBuilder()
            .setOpen(defaultPrice)
            .setHigh(defaultPrice)
            .setLow(defaultPrice)
            .setClose(defaultPrice)
            .setVolume(0.0)
            .setCurrencyPair(currencyPair)
            .setTimestamp(protoTimestamp) // Use the validated & converted timestamp

        return builder.build()
    }

    private fun candleToString(candle: Candle): String {
        return "Candle{Pair:${candle.currencyPair}, T:${Timestamps.toString(candle.timestamp)}, O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
    }
}
