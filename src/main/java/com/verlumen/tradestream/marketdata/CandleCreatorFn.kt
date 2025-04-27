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
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>,
        @TimerId("endOfWindowTimer") timer: Timer,
        window: BoundedWindow
    ) {
        val currencyPair = element.key
        val trade = element.value

        logger.atFine().log("Processing trade for %s: %s in window %s", currencyPair, trade.tradeId, window)

        // Set timer for the end of the window to ensure output even if no more trades arrive
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
            // Update high and low always
            accumulator.high = maxOf(accumulator.high, trade.price)
            accumulator.low = minOf(accumulator.low, trade.price)
            
            // Update open if this is an earlier trade
            if (trade.timestamp.seconds < accumulator.firstTradeTimestamp) {
                accumulator.open = trade.price
                accumulator.firstTradeTimestamp = trade.timestamp.seconds
            }
            
            // Update close if this is a later trade
            if (trade.timestamp.seconds >= accumulator.latestTradeTimestamp) {
                accumulator.close = trade.price
                accumulator.latestTradeTimestamp = trade.timestamp.seconds
            }
            
            // Always add volume
            accumulator.volume += trade.volume
        }

        currentCandleState.write(accumulator)
    }

    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>,
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()
        val lastEmittedCandle = lastCandleState.read()

        try {
            if (accumulator != null && accumulator.initialized) {
                // Case 1: Trades occurred in this window - create an actual candle
                val actualCandle = buildCandleFromAccumulator(accumulator)
                context.output(KV.of(accumulator.currencyPair, actualCandle))
                
                // Update the state with the latest actual candle for future fill-forward
                lastCandleState.write(actualCandle)
                
                logger.atFine().log(
                    "Output actual candle for %s at window end %s: %s",
                    accumulator.currencyPair, window.maxTimestamp(), candleToString(actualCandle)
                )
            } else if (lastEmittedCandle != null) {
                // Case 2: No trades, but we have a previous candle state - create fill-forward
                val key = lastEmittedCandle.currencyPair
                val fillForwardCandle = buildFillForwardCandle(key, lastEmittedCandle, window.maxTimestamp())
                
                // Output the fill-forward candle with the window's max timestamp
                context.outputWithTimestamp(KV.of(key, fillForwardCandle), window.maxTimestamp())
                
                // CRITICAL FIX: Update the state with the fill-forward candle for continuing the chain
                lastCandleState.write(fillForwardCandle)
                
                logger.atFine().log(
                    "Output fill-forward candle for %s at window end %s: %s (based on last close: ${lastEmittedCandle.close})",
                    key, window.maxTimestamp(), candleToString(fillForwardCandle)
                )
            } else {
                // Case 3: No trades and no prior candle history for this key
                logger.atFine().log(
                    "No candle output at window end %s (no trades and no prior candle).",
                    window.maxTimestamp()
                )
            }
        } finally {
            // Always clear the accumulator for the current window
            currentCandleState.clear()
        }
    }

    private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(acc.currencyPair)
            .setOpen(acc.open)
            .setHigh(acc.high)
            .setLow(acc.low)
            .setClose(acc.close)
            .setVolume(acc.volume)
            .setTimestamp(Timestamps.fromSeconds(acc.firstTradeTimestamp))
            .build()
    }

    private fun buildFillForwardCandle(key: String, lastEmittedCandle: Candle, windowEnd: Instant): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromSeconds(windowEnd.getMillis() / 1000))  // Convert to seconds for consistent timestamps
            .setOpen(lastEmittedCandle.close)  // Use last emitted close price
            .setHigh(lastEmittedCandle.close)
            .setLow(lastEmittedCandle.close)
            .setClose(lastEmittedCandle.close)
            .setVolume(0.0) // Zero volume indicates fill-forward
            .build()
    }
}
