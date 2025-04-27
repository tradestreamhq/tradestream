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
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.transforms.windowing.IntervalWindow
import org.apache.beam.sdk.values.KV
import org.joda.time.Instant
import java.io.Serializable

/**
 * A state class to track information needed for fill-forward functionality
 */
data class PreviousCandleState(
    val currencyPair: String,
    val timestamp: Long,
    val closePrice: Double
) : Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    constructor(candle: Candle) : this(
        candle.currencyPair,
        candle.timestamp.seconds,
        candle.close
    )
}

/**
 * Stateful DoFn that aggregates Trades into a single Candle per key per window.
 * When no trades occur in a window but there was a prior candle, it outputs a
 * fill-forward candle with the previous close price and 0 volume.
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

    @StateId("previousCandle")
    private val previousCandleSpec: StateSpec<ValueState<PreviousCandleState>> =
        StateSpecs.value(SerializableCoder.of(PreviousCandleState::class.java))

    @TimerId("endOfWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @Setup
    fun setup() {
        logger.atInfo().log("Setting up CandleCreatorFn with fill-forward capability")
    }

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Trade>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @TimerId("endOfWindowTimer") timer: Timer,
        window: BoundedWindow
    ) {
        val currencyPair = element.key
        val trade = element.value

        logger.atFine().log("Processing trade for %s: %s in window %s", currencyPair, trade.tradeId, window)

        // Set the timer for the end of the current window
        timer.set(window.maxTimestamp())

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

    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @StateId("previousCandle") previousCandleState: ValueState<PreviousCandleState>,
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()
        val previous = previousCandleState.read()

        // Get the key from either the accumulator or the previous candle
        val key = when {
            accumulator != null -> accumulator.currencyPair
            previous != null -> previous.currencyPair
            else -> {
                logger.atFine().log("No key found for window %s", window.maxTimestamp())
                return // No key, no output possible
            }
        }

        if (accumulator != null && accumulator.initialized) {
            // Case 1: Trades occurred in this window - create standard candle
            val newCandle = buildCandleFromAccumulator(accumulator)
            context.outputWithTimestamp(KV.of(key, newCandle), window.maxTimestamp())
            
            // Save this candle's info for potential fill-forward in future windows
            previousCandleState.write(PreviousCandleState(newCandle))
            
            logger.atFine().log(
                "Output actual candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(newCandle)
            )
        } else if (previous != null) {
            // Case 2: No trades in this window, but there was a previous candle - create fill-forward candle
            
            // Check if the window is contiguous with previous
            if (window is IntervalWindow) {
                val windowStart = window.start().getMillis() / 1000 // Convert to seconds
                val prevTimestamp = previous.timestamp
                
                // Check if this window is the next expected window after previous
                // For example, if previous was for 10:00-10:01, then this window should start at 10:01
                val expectedStart = prevTimestamp + (window.end().getMillis() - window.start().getMillis()) / 1000
                
                if (windowStart == expectedStart) {
                    // This is a contiguous window - generate fill-forward candle
                    val fillForwardCandle = buildFillForwardCandle(key, previous, window.maxTimestamp())
                    context.outputWithTimestamp(KV.of(key, fillForwardCandle), window.maxTimestamp())
                    
                    // Update previous state with this new fill-forward candle
                    previousCandleState.write(PreviousCandleState(fillForwardCandle))
                    
                    logger.atFine().log(
                        "Output fill-forward candle for %s at window end %s: %s",
                        key, window.maxTimestamp(), candleToString(fillForwardCandle)
                    )
                }
            }
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

    private fun buildFillForwardCandle(
        key: String, 
        previous: PreviousCandleState, 
        windowEnd: Instant
    ): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromMillis(windowEnd.millis))
            .setOpen(previous.closePrice)
            .setHigh(previous.closePrice)
            .setLow(previous.closePrice)
            .setClose(previous.closePrice)
            .setVolume(0.0)
            .build()
    }
}
