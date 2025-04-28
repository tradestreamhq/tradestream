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
        private const val serialVersionUID = 1L // Keep consistent serialVersionUID

        // Helper function for logging candle details
        private fun candleToString(candle: Candle?): String {
            if (candle == null) return "null"
            return "Candle{Pair:${candle.currencyPair}, T:${Timestamps.toString(candle.timestamp)}, " +
                    "O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
        }
    }

    // State specification for accumulating candle data within a window
    @StateId("currentCandle")
    private val currentCandleSpec: StateSpec<ValueState<CandleAccumulator>> =
        StateSpecs.value(SerializableCoder.of(CandleAccumulator::class.java))

    // State specification for storing the last successfully emitted candle (actual or fill-forward)
    @StateId("lastEmittedCandle")
    private val lastCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    // Timer specification to trigger logic at the end of the event time window
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

        // Set timer for the end of the window. This ensures onWindowEnd is called
        // even if no more trades arrive for this key in this window.
        // The timer is keyed by the element's key implicitly.
        timer.set(window.maxTimestamp())

        // Update the candle accumulator state with the current trade
        processTradeIntoCandle(currencyPair, trade, currentCandleState)
    }

    /**
     * Updates the CandleAccumulator state with the details of a new trade.
     */
    private fun processTradeIntoCandle(
        currencyPair: String,
        trade: Trade,
        currentCandleState: ValueState<CandleAccumulator>
    ) {
        // Read the current accumulator state, or create a new one if it doesn't exist
        var accumulator = currentCandleState.read() ?: CandleAccumulator()

        if (!accumulator.initialized) {
            // First trade for this key-window: Initialize the accumulator
            accumulator.currencyPair = currencyPair
            // Use the *first* trade's timestamp as the representative candle timestamp
            accumulator.timestamp = trade.timestamp.seconds
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.initialized = true
            accumulator.firstTradeTimestamp = trade.timestamp.seconds
            accumulator.latestTradeTimestamp = trade.timestamp.seconds
            logger.atFine().log("Initialized accumulator for %s with trade %s", currencyPair, trade.tradeId)
        } else {
            // Subsequent trade for this key-window: Update the accumulator
            accumulator.high = maxOf(accumulator.high, trade.price)
            accumulator.low = minOf(accumulator.low, trade.price)
            accumulator.volume += trade.volume

            // Update open price if this trade is earlier than the current earliest
            if (trade.timestamp.seconds < accumulator.firstTradeTimestamp) {
                accumulator.open = trade.price
                accumulator.firstTradeTimestamp = trade.timestamp.seconds
            }

            // Update close price if this trade is later than or equal to the current latest
            if (trade.timestamp.seconds >= accumulator.latestTradeTimestamp) {
                accumulator.close = trade.price
                accumulator.latestTradeTimestamp = trade.timestamp.seconds
            }
            logger.atFine().log("Updated accumulator for %s with trade %s", currencyPair, trade.tradeId)
        }

        // Write the updated accumulator back to state
        currentCandleState.write(accumulator)
    }

    /**
     * Called when the event time timer fires, indicating the end of a window.
     * Outputs either an actual candle (if trades occurred) or a fill-forward candle.
     */
    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>,
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()
        val lastEmittedCandle = lastCandleState.read()
        var candleToOutput: Candle? = null
        var key: String? = null

        try {
            // Determine the key for this timer context from available state
            key = accumulator?.currencyPair ?: lastEmittedCandle?.currencyPair

            if (key == null) {
                logger.atWarning().log(
                    "Timer fired for window end %s, but could not determine key (accumulator and lastCandleState were null).",
                    window.maxTimestamp()
                )
                return // Cannot proceed without a key
            }

            logger.atFine().log("Timer fired for key %s, window %s. Accumulator: %s, LastEmitted: %s",
                key, window, accumulator, candleToString(lastEmittedCandle))

            if (accumulator != null && accumulator.initialized) {
                // Case 1: Trades occurred - build actual candle
                candleToOutput = buildCandleFromAccumulator(accumulator)
                logger.atFine().log("Built actual candle for %s: %s", key, candleToString(candleToOutput))

            } else if (lastEmittedCandle != null && lastEmittedCandle.currencyPair == key) {
                 // Case 2: No trades, but have previous state for the *same key* - build fill-forward
                candleToOutput = buildFillForwardCandle(key, lastEmittedCandle, window.maxTimestamp())
                logger.atFine().log("Built fill-forward candle for %s: %s", key, candleToString(candleToOutput))

            } else {
                // Case 3: No trades and no relevant prior history for this key
                logger.atFine().log("No candle to output for key %s at window end %s.", key, window.maxTimestamp())
            }

            // Output the candle and update state *only if* a candle was generated
            if (candleToOutput != null) {
                // Output with the window's end timestamp
                context.outputWithTimestamp(KV.of(key, candleToOutput), window.maxTimestamp())
                // Update the state with the candle that was just outputted
                lastCandleState.write(candleToOutput)
                logger.atFine().log("Outputted and updated lastCandleState for %s with: %s", key, candleToString(candleToOutput))
            }

        } catch (e: Exception) {
            // Log any unexpected errors during timer processing
             logger.atSevere().withCause(e).log("Error processing timer for key %s, window %s", key ?: "UNKNOWN", window)
        }
        finally {
            // Always clear the accumulator state for the current window after processing
            currentCandleState.clear()
            logger.atFine().log("Cleared currentCandleState for key %s, window ending %s", key ?: "UNKNOWN", window.maxTimestamp())
        }
    }


    /**
     * Builds an actual Candle protobuf message from the accumulator state.
     */
    private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(acc.currencyPair)
            .setOpen(acc.open)
            .setHigh(acc.high)
            .setLow(acc.low)
            .setClose(acc.close)
            .setVolume(acc.volume)
            // Use the timestamp of the *first* trade in the window as the candle's timestamp
            .setTimestamp(Timestamps.fromSeconds(acc.firstTradeTimestamp))
            .build()
    }

    /**
     * Builds a fill-forward Candle protobuf message.
     */
    private fun buildFillForwardCandle(key: String, lastEmittedCandle: Candle, windowEnd: Instant): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            // Use the *end* of the window as the timestamp for fill-forward candles
            .setTimestamp(Timestamps.fromMillis(windowEnd.millis))
            .setOpen(lastEmittedCandle.close)  // Use last emitted close price
            .setHigh(lastEmittedCandle.close)
            .setLow(lastEmittedCandle.close)
            .setClose(lastEmittedCandle.close)
            .setVolume(0.0) // Zero volume indicates fill-forward
            .build()
    }
}

// Ensure CandleAccumulator is also Serializable if it wasn't already
class CandleAccumulator : Serializable {
    var currencyPair: String = ""
    var open: Double = 0.0
    var high: Double = Double.NEGATIVE_INFINITY // Initialize high low correctly
    var low: Double = Double.POSITIVE_INFINITY  // Initialize high low correctly
    var close: Double = 0.0
    var volume: Double = 0.0
    var timestamp: Long = 0 // Timestamp of the *first* trade in the window
    var initialized: Boolean = false
    var firstTradeTimestamp: Long = Long.MAX_VALUE // Track earliest trade timestamp
    var latestTradeTimestamp: Long = Long.MIN_VALUE // Track latest trade timestamp for close price

    companion object {
        private const val serialVersionUID = 2L // Increment if structure changes
    }

    override fun toString(): String {
        return "CandleAccumulator{initialized=$initialized, pair='$currencyPair', open=$open, high=$high, " +
                "low=$low, close=$close, volume=$volume, candleTs=$timestamp, firstTradeTs=$firstTradeTimestamp, lastTradeTs=$latestTradeTimestamp}"
    }
}
