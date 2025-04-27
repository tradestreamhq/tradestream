package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
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
import org.joda.time.Instant
import java.io.Serializable

/**
 * Stateful DoFn that aggregates Trades into a single Candle per key per window.
 * When no trades occur in a window, it uses the previous candle's close price to create
 * a continuation candle with zero volume.
 */
class CandleCreatorFn @Inject constructor() :
    DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {

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

    /**
     * Special state flag to determine if we need to register interest in future windows,
     * which is needed for creating fill-forward candles when no trades occur.
     */
    @StateId("needsFutureWindows")
    private val needsFutureWindowsSpec: StateSpec<ValueState<Boolean>> =
        StateSpecs.value(SerializableCoder.of(Boolean::class.java))

    @TimerId("endOfWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)
    
    @TimerId("ensureFutureWindowTimer")
    private val futureWindowTimerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @Setup
    fun setup() {
        logger.atInfo().log("Setting up CandleCreatorFn with fill-forward capability")
    }

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Trade>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>,
        @StateId("needsFutureWindows") needsFutureWindowsState: ValueState<Boolean>,
        @TimerId("endOfWindowTimer") timer: Timer,
        @TimerId("ensureFutureWindowTimer") futureWindowTimer: Timer,
        window: BoundedWindow
    ) {
        val currencyPair = element.key
        val trade = element.value

        logger.atFine().log("Processing trade for %s: %s in window %s", currencyPair, trade.tradeId, window)

        timer.set(window.maxTimestamp())
        
        // If this is the first time we've seen this key or we already know we want future windows
        if (lastCandleState.read() != null || needsFutureWindowsState.read() == true) {
            // Mark that we want to receive future windows for this key
            needsFutureWindowsState.write(true)
            
            // Set a timer for the next window to ensure we get called even if there are no elements
            // We add 1ms to ensure it's in the next window
            val nextWindowStart = window.maxTimestamp().plus(1) 
            futureWindowTimer.set(nextWindowStart)
            
            logger.atFine().log("Setting future window timer for %s at %s", currencyPair, nextWindowStart)
        }

        processTradeIntoCandle(currencyPair, trade, currentCandleState)
    }

    private fun processTradeIntoCandle(
        currencyPair: String,
        trade: Trade,
        currentCandleState: ValueState<CandleAccumulator>
    ) {
        var accumulator = currentCandleState.read()

        if (accumulator == null || !accumulator.initialized) {
            // First trade for this key-window
            accumulator = CandleAccumulator()
            accumulator.currencyPair = currencyPair
            accumulator.timestamp = trade.timestamp.seconds
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.initialized = true
            accumulator.firstTradeTimestamp = trade.timestamp.seconds
            accumulator.latestTradeTimestamp = trade.timestamp.seconds
        } else {
            // Check if this is an earlier trade than what we've seen
            if (trade.timestamp.seconds < accumulator.firstTradeTimestamp) {
                // This is actually the earliest trade we've seen, use as open
                accumulator.open = trade.price
                accumulator.firstTradeTimestamp = trade.timestamp.seconds
            }

            // Check if this is the latest trade we've seen
            if (trade.timestamp.seconds >= accumulator.latestTradeTimestamp) {
                // This is the latest trade, use for close price
                accumulator.close = trade.price
                accumulator.latestTradeTimestamp = trade.timestamp.seconds
            }

            // Always update high, low and volume
            accumulator.high = maxOf(accumulator.high, trade.price)
            accumulator.low = minOf(accumulator.low, trade.price)
            accumulator.volume += trade.volume
        }

        currentCandleState.write(accumulator)
    }

    @OnTimer("ensureFutureWindowTimer")
    fun onFutureWindowTimer(
        context: OnTimerContext,
        @TimerId("endOfWindowTimer") endOfWindowTimer: Timer,
        window: BoundedWindow,
        @StateId("needsFutureWindows") needsFutureWindowsState: ValueState<Boolean>,
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>
    ) {
        // If we still need future windows (have lastEmittedCandle state),
        // set the endOfWindow timer for this window to ensure we either output
        // a regular candle or a fill-forward candle
        if (lastCandleState.read() != null) {
            endOfWindowTimer.set(window.maxTimestamp())
            
            // Set a timer for the next window too
            val nextWindowStart = window.maxTimestamp().plus(1)
            context.timer("ensureFutureWindowTimer").set(nextWindowStart)
            
            logger.atFine().log("Future window timer: Set end-of-window timer for window %s", window)
        } else {
            // No more history, we can stop tracking this key
            needsFutureWindowsState.clear()
            logger.atFine().log("Future window timer: No lastEmittedCandle, stopping future windows")
        }
    }

    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>,
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()
        val lastCandle = lastCandleState.read()
        
        // Get the key from either the accumulator or the last candle
        val key = when {
            accumulator != null -> accumulator.currencyPair
            lastCandle != null -> lastCandle.currencyPair
            else -> {
                logger.atFine().log("No key found for window %s", window.maxTimestamp())
                return // No key, no output possible
            }
        }

        logger.atFine().log("Processing end of window for %s at %s (has accumulator: %s, has lastCandle: %s)", 
            key, window.maxTimestamp(), accumulator != null, lastCandle != null)

        if (accumulator != null && accumulator.initialized) {
            // Case 1: Trades occurred in this window - create standard candle
            val newCandle = buildCandleFromAccumulator(accumulator)
            context.outputWithTimestamp(KV.of(key, newCandle), window.maxTimestamp())
            lastCandleState.write(newCandle) // Update last emitted candle state
            logger.atFine().log(
                "Output actual candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(newCandle)
            )
        } else if (lastCandle != null) {
            // Case 2: No trades in this window, but there was a previous candle - create fill-forward candle
            val fillForwardCandle = buildFillForwardCandle(key, lastCandle, window.maxTimestamp())
            context.outputWithTimestamp(KV.of(key, fillForwardCandle), window.maxTimestamp())
            lastCandleState.write(fillForwardCandle) // Update with the new fill-forward candle for future windows
            logger.atFine().log(
                "Output fill-forward candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(fillForwardCandle)
            )
        } else {
            // Case 3: No trades in this window AND no previous candle history - output nothing
            val reason = when {
                accumulator == null -> "no accumulator found"
                !accumulator.initialized -> "accumulator not initialized"
                else -> "unknown reason"
            }
            logger.atFine().log(
                "No candle output for key '%s' at window end %s (%s and no prior candle).",
                key, window.maxTimestamp(), reason
            )
        }

        // Always clear the accumulator for the current window
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

        // Use the first trade timestamp for the candle timestamp
        builder.setTimestamp(Timestamps.fromSeconds(acc.firstTradeTimestamp))

        return builder.build()
    }

    private fun buildFillForwardCandle(key: String, lastCandle: Candle, windowEnd: Instant): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromMillis(windowEnd.millis))
            .setOpen(lastCandle.close)
            .setHigh(lastCandle.close)
            .setLow(lastCandle.close)
            .setClose(lastCandle.close)
            .setVolume(0.0)
            .build()
    }
}
