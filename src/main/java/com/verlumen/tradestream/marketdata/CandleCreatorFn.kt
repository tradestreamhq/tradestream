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
        val lastEmittedCandle = lastCandleState.read() // Read the candle emitted in the previous window

        // Determine the key (currency pair)
        val key = when {
            accumulator != null && accumulator.initialized -> accumulator.currencyPair
            lastEmittedCandle != null -> lastEmittedCandle.currencyPair
            else -> {
                logger.atFine().log("No key found for window %s, cannot output.", window.maxTimestamp())
                // Clear states for this window as no output is possible
                currentCandleState.clear()
                // Consider if lastCandleState should be cleared too, depends on desired behavior after a complete gap
                // lastCandleState.clear()
                return
            }
        }

        val candleToOutput: Candle?
        val candleToRemember: Candle? // This is the candle state we'll store for the *next* window

        if (accumulator != null && accumulator.initialized) {
            // Case 1: Trades occurred in this window. Output a standard candle.
            val actualCandle = buildCandleFromAccumulator(accumulator)
            candleToOutput = actualCandle
            candleToRemember = actualCandle // Remember this actual candle's state
            logger.atFine().log(
                "Output actual candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(actualCandle)
            )
        } else if (lastEmittedCandle != null) {
            // Case 2: No trades, but there was a previously emitted candle. Output a fill-forward candle.
            val fillForwardCandle = buildFillForwardCandle(key, lastEmittedCandle, window.maxTimestamp())
            candleToOutput = fillForwardCandle
            // IMPORTANT: Remember the state of the fill-forward candle itself for the next window.
            // Its close price (which is the same as lastEmittedCandle's close) will be used if the next window is also empty.
            candleToRemember = fillForwardCandle
            logger.atFine().log(
                "Output fill-forward candle for %s at window end %s: %s",
                key, window.maxTimestamp(), candleToString(fillForwardCandle)
            )
        } else {
            // Case 3: No trades in this window AND no previous candle history for this key. Output nothing.
            candleToOutput = null
            candleToRemember = null // Nothing to remember
            logger.atFine().log(
                "No candle output for key '%s' at window end %s (no trades and no prior candle).",
                key, window.maxTimestamp()
            )
        }

        // Output the candle determined above (if any)
        candleToOutput?.let {
            context.outputWithTimestamp(KV.of(key, it), window.maxTimestamp())
        }

        // Update the state for the next window's potential fill-forward
        if (candleToRemember != null) {
             lastCandleState.write(candleToRemember)
        } else {
             // If we are in Case 3 (output nothing), clear the state
             // so we don't incorrectly fill-forward across a large gap
             // where no candles were produced at all.
             lastCandleState.clear()
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
