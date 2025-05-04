package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
import java.io.Serializable
import java.util.ArrayList
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.SerializableCoder
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
import org.apache.beam.sdk.transforms.DoFn.OnTimer
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.transforms.DoFn.TimerId
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TypeDescriptor
import org.apache.beam.sdk.values.TypeDescriptors
import org.joda.time.Duration
import org.joda.time.Instant

/**
 * PTransform that aggregates Trades into Candles using a stateful DoFn with event time timers.
 * Handles gaps by potentially outputting fill-forward candles.
 */
class TradeToCandle
@Inject
constructor(
    @Assisted private val candleInterval: Duration,
    private val candleCombineFn: CandleCombineFn // Keep CombineFn dependency
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        // Increment version due to timer logic change
        private const val serialVersionUID = 7L // Incremented version
    }

    interface Factory {
        fun create(candleInterval: Duration): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        val keyed: PCollection<KV<String, Trade>> =
            input.apply<PCollection<KV<String, Trade>>>(
                    "KeyByPair",
                    MapElements.into<KV<String, Trade>>(
                            TypeDescriptors.kvs(
                                TypeDescriptors.strings(),
                                TypeDescriptor.of(Trade::class.java)
                            )
                        )
                        .via(SerializableFunction { t: Trade -> KV.of(t.currencyPair, t) })
                )
                .setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade::class.java)))

        return keyed.apply(
                    "StatefulCandle",
                    ParDo.of(StatefulTradeProcessor(candleInterval, candleCombineFn))
                )
                .setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
    }

    private class StatefulTradeProcessor(
        private val candleInterval: Duration,
        private val candleCombineFn: CandleCombineFn
    ) : DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID = 7L // Incremented version
            private const val INTERVAL_END_TIMER = "intervalEndTimer"

            // Helper function for logging candle details
            private fun candleToString(candle: Candle?): String {
                if (candle == null || candle == Candle.getDefaultInstance()) return "null"
                return "Candle{Pair=${candle.currencyPair}, " +
                    "T=${Timestamps.toString(candle.timestamp)}, " +
                    "O=${candle.open}, H=${candle.high}, L=${candle.low}, " +
                    "C=${candle.close}, V=${candle.volume}}"
            }
        }

        @StateId("trades")
        private val tradesStateSpec: StateSpec<ValueState<ArrayList<Trade>>> =
            StateSpecs.value(SerializableCoder.of(ArrayList::class.java) as Coder<ArrayList<Trade>>)

        @StateId("currentIntervalEnd")
        private val intervalEndStateSpec: StateSpec<ValueState<Instant>> =
            StateSpecs.value(SerializableCoder.of(Instant::class.java))

        @StateId("lastCandle")
        private val lastCandleStateSpec: StateSpec<ValueState<Candle>> =
            StateSpecs.value(ProtoCoder.of(Candle::class.java))

        @TimerId(INTERVAL_END_TIMER)
        private val intervalEndTimerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

        // Helper to get interval boundary
        private fun getIntervalEnd(timestamp: Instant): Instant {
            val ms = timestamp.millis
            val intervalMillis = candleInterval.millis
            // Calculate the end of the interval containing the timestamp
            return Instant((ms / intervalMillis) * intervalMillis + intervalMillis)
        }

        // Helper to build or fill-forward a candle
        private fun buildOrFillCandle(
            trades: List<Trade>,
            lastCandleState: ValueState<Candle>,
            intervalEndForFill: Instant // Needed for logging consistency
        ): Candle? {
            return if (trades.isNotEmpty()) {
                // Build from trades
                logger.atFine().log("Building candle from ${trades.size} trades for interval ending $intervalEndForFill.")
                val acc = candleCombineFn.createAccumulator()
                trades.forEach { candleCombineFn.addInput(acc, it) }
                // Extract candle but DON'T set timestamp yet. It's set in output helpers.
                candleCombineFn.extractOutput(acc)
            } else {
                // Fill-forward
                val lastActualCandle = lastCandleState.read()
                if (lastActualCandle != null && lastActualCandle != Candle.getDefaultInstance()) {
                    logger.atFine().log(
                        "Filling forward for interval $intervalEndForFill using last candle closed at ${Timestamps.toString(lastActualCandle.timestamp)}: ${candleToString(lastActualCandle)}"
                    )
                    // Create a new candle based on the last actual one.
                    // OHLC = last close, V = 0. Timestamp will be set later.
                    lastActualCandle
                        .toBuilder()
                        .setOpen(lastActualCandle.close)
                        .setHigh(lastActualCandle.close)
                        .setLow(lastActualCandle.close)
                        // Close is already set from previous candle's close
                        .setVolume(0.0) // Explicitly set volume to zero for fill-forward
                        // CurrencyPair is inherited
                        .build()
                } else {
                    logger.atFine().log("Attempted fill-forward for interval $intervalEndForFill, but no valid last candle found.")
                    null // Return null if no valid last candle exists
                }
            }
        }

        // Helper to output candle - sets final timestamp and updates state
        private fun outputCandle(
            outputReceiver: OutputReceiver<KV<String, Candle>>,
            timestampToOutput: Instant, // Beam element timestamp (usually timer fire time or triggering element time)
            key: String,
            candle: Candle,
            intervalEnd: Instant, // The actual end time of the candle interval
            lastCandleState: ValueState<Candle>,
            contextType: String // "process" or "timer" for logging
        ) {
             if (candle == Candle.getDefaultInstance()) {
                logger.atFine().log(
                    "Attempted to output default instance ($contextType) for key $key at $intervalEnd, skipping."
                )
                return
            }

            // Set the candle's *data* timestamp to the interval end time
            val finalCandle = candle.toBuilder()
                .setTimestamp(Timestamps.fromMillis(intervalEnd.millis))
                .setCurrencyPair(key) // Ensure currency pair is set correctly
                .build()

            // Check again if the builder somehow resulted in default (highly unlikely)
            if (finalCandle == Candle.getDefaultInstance()){
                 logger.atWarning().log(
                    "Final candle ($contextType) for key $key at $intervalEnd became default instance unexpectedly, skipping."
                )
                return
            }

            logger.atInfo().log(
                "Outputting candle ($contextType) for key $key at interval end $intervalEnd (Output Timestamp: $timestampToOutput): ${candleToString(finalCandle)}"
            )
            // Output with the Beam element timestamp
            outputReceiver.outputWithTimestamp(KV.of(key, finalCandle), timestampToOutput)
            // Update last *outputted* candle state - use the finalCandle with the correct timestamp
            lastCandleState.write(finalCandle)
        }


        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("trades") tradesState: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEndState: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>,
            @TimerId(INTERVAL_END_TIMER) intervalEndTimer: Timer
        ) {
            val kv = context.element()
            val key = kv.key
            val trade = kv.value
            val tradeTimestamp = context.timestamp() // Use element timestamp for logic
            logger.atFine().log("Processing trade for key $key at $tradeTimestamp: P=${trade.price}, V=${trade.volume}")

            var currentTrades = tradesState.read() ?: ArrayList()
            var currentIntervalEnd = currentIntervalEndState.read()
            val tradeIntervalEnd = getIntervalEnd(tradeTimestamp)

            // Initialize state and timer if this is the first trade for this key
            if (currentIntervalEnd == null) {
                currentIntervalEnd = tradeIntervalEnd
                logger.atInfo().log("Initializing state for key $key. First trade interval end: $currentIntervalEnd. Setting timer.")
                currentIntervalEndState.write(currentIntervalEnd)
                intervalEndTimer.set(currentIntervalEnd)
            }

            // Process completed intervals if the trade is from a future interval
            while (currentIntervalEnd != null && tradeIntervalEnd.isAfter(currentIntervalEnd)) {
                logger.atInfo().log(
                    "Trade for key $key at $tradeTimestamp (interval end $tradeIntervalEnd) is after current interval end $currentIntervalEnd. Finalizing interval."
                )

                // Emit candle for the completed interval (build or fill)
                // Pass currentIntervalEnd for logging within buildOrFillCandle
                val candleToEmit = buildOrFillCandle(currentTrades, lastCandleState, currentIntervalEnd)
                if (candleToEmit != null) {
                    // Output candle. Use the trade's timestamp as the Beam element output timestamp,
                    // as this reflects when the decision to finalize the previous interval was made.
                     outputCandle(context, context.timestamp(), key, candleToEmit, currentIntervalEnd, lastCandleState, "process")
                } else {
                    logger.atFine().log(
                        "No candle to emit during process loop for key $key at interval end $currentIntervalEnd (no trades in buffer, no prior state)."
                    )
                }

                // Clear trades for the completed interval
                currentTrades.clear() // Clear the local list

                // Move state to the next interval
                val nextIntervalEnd = currentIntervalEnd.plus(candleInterval)
                currentIntervalEndState.write(nextIntervalEnd) // Update state
                intervalEndTimer.set(nextIntervalEnd) // Set timer for the *next* interval end
                logger.atInfo().log(
                    "Advanced state for key $key. New interval end: $nextIntervalEnd. Set timer."
                )
                currentIntervalEnd = nextIntervalEnd // Update local variable for loop condition
            }

            // Add the current trade to the buffer IF it belongs to the CURRENT interval
            // This check ensures we don't add trades from the past if state somehow got ahead (e.g., late data handled leniently)
            // And also handles the case where the trade triggered interval finalization just above.
            if (currentIntervalEnd != null && tradeIntervalEnd.isEqual(currentIntervalEnd)) {
                currentTrades.add(trade)
                tradesState.write(currentTrades) // Write updated buffer to state
                logger.atFine().log("Added trade to buffer for key $key. Buffer size: ${currentTrades.size} for interval $currentIntervalEnd")
            } else if (currentIntervalEnd != null && tradeTimestamp.isBefore(currentIntervalEnd.minus(candleInterval))) {
                // This trade is "late" relative to the *current* state interval end.
                // We could ignore it, process it if the watermark allows, or buffer it separately.
                // Current behavior: It won't be added to `currentTrades` because `tradeIntervalEnd` won't match `currentIntervalEnd`.
                // It will effectively be dropped unless Beam's allowed lateness handles it.
                logger.atWarning().log(
                    "Trade $tradeTimestamp arrived late for key $key. Current interval end in state is $currentIntervalEnd. Trade belongs to $tradeIntervalEnd. Ignoring for current buffer."
                    )
            } else if (currentIntervalEnd == null) {
                 logger.atError().log("State error: currentIntervalEnd is null after initialization/loop for key $key. Trade at $tradeTimestamp cannot be processed.")
            } else {
                 // Should not happen if loop logic is correct
                 logger.atWarning().log("Trade $tradeTimestamp for key $key did not match expected interval $currentIntervalEnd (trade belongs to $tradeIntervalEnd). State might be inconsistent.")
            }
        }

        @OnTimer(INTERVAL_END_TIMER)
        fun onTimer(
            context: OnTimerContext, // Correct type for @OnTimer
            @StateId("trades") tradesState: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEndState: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>,
            @TimerId(INTERVAL_END_TIMER) intervalEndTimer: Timer
        ) {
            val timerFireTimestamp = context.timestamp() // This IS the interval end the timer was set for
            val expectedIntervalEnd = currentIntervalEndState.read() // Read the state value

            // If state is missing or timer is for an old interval (shouldn't happen with correct logic but good safeguard), ignore
            if (expectedIntervalEnd == null || !timerFireTimestamp.isEqual(expectedIntervalEnd)) {
                 logger.atWarning().log(
                     "Ignoring timer fired at %s. Expected interval end from state: %s. State might be missing or timer is late/spurious.",
                     timerFireTimestamp, expectedIntervalEnd ?: "null"
                 )
                 // Do NOT set the next timer here if ignoring the current one.
                 // If expectedIntervalEnd exists but doesn't match, maybe clear state? Risky. Let's just ignore.
                 if (expectedIntervalEnd == null) {
                     tradesState.clear() // Clear trades if interval state is gone
                 }
                 return
            }

            // State matches timer, proceed. 'expectedIntervalEnd' is the end of the interval we are processing.
            val intervalEnd = expectedIntervalEnd // Use a clearer name for this specific interval end

            val trades = tradesState.read() ?: ArrayList()
            val lastCandle = lastCandleState.read() // Read last successfully output candle

            // Derive key - crucial for outputting KV and next timer logic
            // Try trades first, then last candle state.
            val key = trades.firstOrNull()?.currencyPair ?: lastCandle?.currencyPair

             if (key == null || key.isEmpty()) {
                 logger.atWarning().log(
                     "Timer fired at %s but cannot determine key (no trades in buffer [%s] and no valid last candle [%s]). Clearing state and stopping timer chain for this (unknown) key.",
                      timerFireTimestamp, trades.size, candleToString(lastCandle)
                 )
                 tradesState.clear()
                 currentIntervalEndState.clear() // Clear interval state as we cannot proceed
                 // Do not set the next timer
                 return
             }

            logger.atInfo().log(
                "Timer fired for key %s at interval end %s. Processing interval. Trades in buffer: %s. Last Output Candle: %s",
                key, intervalEnd, trades.size, candleToString(lastCandle)
            )

            // Build or fill-forward the candle for the interval that just ended.
            // Pass intervalEnd for logging consistency inside buildOrFillCandle.
            val candleToEmit = buildOrFillCandle(trades, lastCandleState, intervalEnd)

            if (candleToEmit != null) {
                 // Output the candle for the interval that just ended
                 // Use the timer fire timestamp as the Beam element timestamp
                 outputCandle(context, context.timestamp(), key, candleToEmit, intervalEnd, lastCandleState, "timer")
            } else {
                 logger.atInfo().log( // Changed to Info level - this is expected for gaps
                    "Timer fired for key %s at interval end %s, but no candle could be generated (no trades in buffer and no prior state for fill-forward). No output for this interval.",
                    key, intervalEnd
                 )
                 // Even if we don't output, we still need to set the timer for the *next* interval
                 // to continue checking for potential trades or fill-forward opportunities.
            }

            // --- State Update and Next Timer ---
            // 1. Clear trades state for the processed interval
            tradesState.clear()

            // 2. Calculate the end of the *next* interval
            val nextIntervalEnd = intervalEnd.plus(candleInterval)

            // 3. Update the state to reflect the *next* interval end we expect
            currentIntervalEndState.write(nextIntervalEnd)

            // 4. Set the timer to fire at the end of that *next* interval
            intervalEndTimer.set(nextIntervalEnd)
            // --- End State Update ---

            logger.atInfo().log(
                "Timer processed for key %s at %s. Trades state cleared. Set next interval end state to %s and timer for %s.",
                key, intervalEnd, nextIntervalEnd, nextIntervalEnd
            )
        }
    }
}
