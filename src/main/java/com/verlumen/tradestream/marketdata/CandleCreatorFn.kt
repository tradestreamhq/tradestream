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
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>, // State to remember the last output candle
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()
        val lastActualCandleFromState = lastCandleState.read() // Read the *actual* candle emitted previously

        val key = when {
            accumulator != null && accumulator.initialized -> accumulator.currencyPair
            lastActualCandleFromState != null -> lastActualCandleFromState.currencyPair // Use key from last actual candle
            else -> {
                logger.atFine().log("No key found for window %s, cannot output.", window.maxTimestamp())
                currentCandleState.clear()
                // Decide if lastCandleState should be cleared depending on desired behavior for long gaps
                // lastCandleState.clear()
                return
            }
        }

        val candleToOutput: Candle?

        if (accumulator != null && accumulator.initialized) {
            // Case 1: Trades occurred. Output actual candle and update the last emitted state.
            val actualCandle = buildCandleFromAccumulator(accumulator)
            candleToOutput = actualCandle
            lastCandleState.write(actualCandle) // <<< CHANGE: Store the ACTUAL candle state
            logger.atFine().log(
                "Output actual candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(actualCandle)
            )
        } else if (lastActualCandleFromState != null) {
            // Case 2: No trades, but previous actual candle exists. Output fill-forward.
            // Ensure lastActualCandleFromState is indeed available before trying to build fill-forward
            if (lastActualCandleFromState != null) {
                val fillForwardCandle = buildFillForwardCandle(key, lastActualCandleFromState, window.maxTimestamp())
                candleToOutput = fillForwardCandle
                // State retains lastActualCandleFromState.
            } else { // Should not happen based on else if condition, but defensive
                candleToOutput = null
            }
            logger.atFine().log(
                "Output fill-forward candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(fillForwardCandle)
            )
        } else {
            // Case 3: No trades and no prior actual candle. Output nothing.
            candleToOutput = null
            lastCandleState.clear() // Clear state if there's a gap with no history
            logger.atInfo().log( // Changed to info to highlight this path
                "No candle output for key '%s' at window end %s (no trades and no prior candle).",
                key, window.maxTimestamp()
            )
        }

        // Output the candle determined above (if any)
        candleToOutput?.let {
            context.outputWithTimestamp(KV.of(key, it), window.maxTimestamp())
        }

        // Always clear the trade accumulator for the current window
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
