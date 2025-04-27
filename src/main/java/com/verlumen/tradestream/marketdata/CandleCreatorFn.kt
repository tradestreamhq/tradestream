package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted // Added import
import com.google.protobuf.util.Timestamps
import org.apache.beam.sdk.coders.SerializableCoder
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
import org.joda.time.Duration // Added import
import org.joda.time.Instant
import java.io.Serializable
import kotlin.math.max // Ensure these are imported if needed
import kotlin.math.min // Ensure these are imported if needed


/**
 * Stateful DoFn that aggregates Trades into a single Candle per key per window.
 * When no trades occur in a window, it uses the previous candle's close price to create
 * a continuation candle with zero volume. It proactively sets a timer for the next window.
 */
class CandleCreatorFn @Inject constructor(
    @Assisted private val windowDuration: Duration // Inject windowDuration
) : DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {

    // Factory interface for AssistedInject
    interface Factory {
        fun create(windowDuration: Duration): CandleCreatorFn
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L

        private fun candleToString(candle: Candle): String {
            return "Candle{Pair:${candle.currencyPair}, T:${Timestamps.toString(candle.timestamp)}, " +
                   "O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
        }
    }

    @StateId("currentCandle")
    private val currentCandleSpec: StateSpec<ValueState<CandleAccumulator>> =
        StateSpecs.value(SerializableCoder.of(CandleAccumulator::class.java))

    @StateId("lastEmittedCandle")
    private val lastCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    @TimerId("endOfWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @Setup
    fun setup() {
        logger.atInfo().log("Setting up CandleCreatorFn with fill-forward capability and proactive timer")
    }

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        window: BoundedWindow,
        @Element element: KV<String, Trade>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @TimerId("endOfWindowTimer") timer: Timer // Add Timer parameter
    ) {
        val currencyPair = element.key
        val trade = element.value
        logger.atFinest().log("Processing trade for %s at %s in window %s",
            currencyPair, Timestamps.toString(trade.timestamp), window.maxTimestamp())

        var accumulator = currentCandleState.read()

        if (accumulator == null || !accumulator.initialized) {
            // First trade for this key-window
            accumulator = CandleAccumulator()
            accumulator.currencyPair = currencyPair
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.initialized = true
            accumulator.firstTradeTimestamp = trade.timestamp.seconds
            accumulator.latestTradeTimestamp = trade.timestamp.seconds
             // Set the candle timestamp for the accumulator (used only if trades exist)
            accumulator.timestamp = trade.timestamp.seconds // Start with first trade time
        } else {
            // Check if this is an earlier trade than what we've seen
            if (trade.timestamp.seconds < accumulator.firstTradeTimestamp) {
                accumulator.open = trade.price
                accumulator.firstTradeTimestamp = trade.timestamp.seconds
                 // Update candle timestamp if this trade is earlier
                accumulator.timestamp = trade.timestamp.seconds
            }

            // Check if this is the latest trade we've seen
            if (trade.timestamp.seconds >= accumulator.latestTradeTimestamp) {
                accumulator.close = trade.price
                accumulator.latestTradeTimestamp = trade.timestamp.seconds
            }

            // Always update high, low and volume
            accumulator.high = max(accumulator.high, trade.price)
            accumulator.low = min(accumulator.low, trade.price)
            accumulator.volume += trade.volume
        }

        currentCandleState.write(accumulator)

        // Set the timer for the end of the *current* window.
        // This ensures onWindowEnd is called at least once if trades arrive.
        // The onWindowEnd method will then set the timer for the *next* window.
        logger.atFinest().log("Setting timer for window end: %s", window.maxTimestamp())
        timer.set(window.maxTimestamp())
    }

    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>,
        @TimerId("endOfWindowTimer") timer: Timer, // Add Timer parameter
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()
        val lastCandle = lastCandleState.read()
        val currentWindowEnd = window.maxTimestamp()
        logger.atFine().log("Timer fired for window end %s. Acc initialized: %s, LastCandle exists: %s",
                currentWindowEnd, accumulator?.initialized ?: false, lastCandle != null)

        // Determine the key - needed for logging and potentially for fill-forward
        val key = when {
            accumulator != null && accumulator.initialized -> accumulator.currencyPair
            lastCandle != null -> lastCandle.currencyPair
            else -> null // Cannot determine key if no trades and no history
        }

        if (key == null) {
             logger.atFine().log("Cannot determine key for window ending %s. No accumulator and no prior candle. Skipping.", currentWindowEnd)
             // If key is null, we cannot set a keyed timer for the next window. This implies
             // no trades ever occurred for this potential key in any prior window, so fill-forward
             // isn't possible anyway. We also didn't set a timer in processElement.
        } else {
            // Process the current window
            if (accumulator != null && accumulator.initialized) {
                // Case 1: Trades occurred in this window - create standard candle
                val newCandle = buildCandleFromAccumulator(accumulator)
                // Output with the timestamp of the *end* of the window it represents
                context.outputWithTimestamp(KV.of(key, newCandle), currentWindowEnd)
                lastCandleState.write(newCandle) // Update last emitted candle state
                logger.atFine().log(
                    "Output actual candle for %s at window end %s: %s",
                    key, currentWindowEnd, candleToString(newCandle)
                )
            } else if (lastCandle != null) {
                // Case 2: No trades in this window, but there was a previous candle
                val fillForwardCandle = buildFillForwardCandle(key, lastCandle, currentWindowEnd)
                // Output with the timestamp of the *end* of the window it represents
                context.outputWithTimestamp(KV.of(key, fillForwardCandle), currentWindowEnd)
                lastCandleState.write(fillForwardCandle) // Update last candle for future fill-forwards
                logger.atFine().log(
                    "Output fill-forward candle for %s at window end %s: %s",
                    key, currentWindowEnd, candleToString(fillForwardCandle)
                )
            } else {
                // Case 3: No trades in this window AND no previous candle history - output nothing
                val reason = if (accumulator == null) "no accumulator found" else "accumulator not initialized"
                logger.atFine().log(
                    "No candle output for key '%s' at window end %s (%s and no prior candle).",
                    key, currentWindowEnd, reason
                )
                // Don't update lastCandleState - there's no history yet
            }

            // *** CRITICAL FIX ***
            // Always set the timer for the *next* window's end boundary, regardless
            // of whether we outputted a candle in *this* window, provided we could determine a key.
            // This ensures the timer callback fires even for subsequent empty windows.
            val nextWindowEnd = currentWindowEnd.plus(windowDuration)
            // Sanity check: Ensure nextWindowEnd is after currentWindowEnd
            if (nextWindowEnd.isAfter(currentWindowEnd)) {
                 logger.atFine().log("Setting timer for NEXT window end: %s for key %s", nextWindowEnd, key)
                 timer.set(nextWindowEnd)
            } else {
                 logger.atWarning().log("Skipping setting timer for key %s as next window end (%s) is not after current window end (%s). This might happen at the end of time or with very small durations.",
                    key, nextWindowEnd, currentWindowEnd)
            }
        }

        // Always clear the accumulator state for the current window
        currentCandleState.clear()
    }


    private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
        val builder = Candle.newBuilder()
            .setOpen(acc.open)
            .setHigh(acc.high)
            .setLow(acc.low)
            .setClose(acc.close)
            .setVolume(acc.volume)
            .setCurrencyPair(acc.currencyPair)

        // Use the first trade timestamp for the candle's representative internal timestamp
        // Although we output with window.maxTimestamp, the candle data reflects the trades within.
        builder.setTimestamp(Timestamps.fromSeconds(acc.timestamp))

        return builder.build()
    }

    private fun buildFillForwardCandle(key: String, lastCandle: Candle, windowEnd: Instant): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromMillis(windowEnd.millis)) // Timestamp is the end of the empty window
            .setOpen(lastCandle.close) // O=H=L=C = previous close
            .setHigh(lastCandle.close)
            .setLow(lastCandle.close)
            .setClose(lastCandle.close)
            .setVolume(0.0) // Zero volume indicates fill-forward
            .build()
    }
}
