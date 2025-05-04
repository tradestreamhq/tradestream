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
        private const val serialVersionUID = 6L
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
            private const val serialVersionUID = 6L // Increment version
            private const val INTERVAL_END_TIMER = "intervalEndTimer" // Renamed timer ID

            // Helper function for logging candle details
            private fun candleToString(candle: Candle?): String {
                if (candle == null) return "null"
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
            return Instant(
                (ms / intervalMillis) * intervalMillis + intervalMillis
            )
        }

        // Helper to build or fill-forward a candle
        private fun buildOrFillCandle(
            trades: List<Trade>,
            lastCandleState: ValueState<Candle>
        ): Candle? {
            return if (trades.isNotEmpty()) {
                // Build from trades
                logger.atFine().log("Building candle from ${trades.size} trades.")
                val acc = candleCombineFn.createAccumulator()
                trades.forEach { candleCombineFn.addInput(acc, it) }
                candleCombineFn.extractOutput(acc)
            } else {
                // Fill-forward
                val lastActualCandle = lastCandleState.read()
                if (lastActualCandle != null && lastActualCandle != Candle.getDefaultInstance()) {
                    logger.atFine().log(
                        "Filling forward using last candle: ${candleToString(lastActualCandle)}"
                    )
                    // Create a new candle based on the last actual one, but set volume to zero
                    // and keep OHLC the same (as last close)
                    // Timestamp will be set by the calling function (outputCandle...)
                    lastActualCandle
                        .toBuilder()
                        .setOpen(lastActualCandle.close)
                        .setHigh(lastActualCandle.close)
                        .setLow(lastActualCandle.close)
                        .setVolume(0.0) // Explicitly set volume to zero for fill-forward
                        .build()
                } else {
                    logger.atFine().log("Attempted fill-forward, but no valid last candle found.")
                    null // Return null if no valid last candle exists
                }
            }
        }

        // Helper to output candle from ProcessContext
        private fun outputCandleFromProcessContext(
            context: ProcessContext,
            key: String,
            candle: Candle,
            intervalEnd: Instant, // Not nullable here
            lastCandleState: ValueState<Candle>
        ) {
            if (candle == Candle.getDefaultInstance()) {
                logger.atFine().log(
                    "Attempted to output default instance for key $key at $intervalEnd, skipping."
                )
                return
            }

            // Set the candle timestamp to the interval end time
            val finalCandle =
                candle.toBuilder().setTimestamp(Timestamps.fromMillis(intervalEnd.millis)).build()

            logger.atInfo().log(
                "Outputting candle (process) for key $key at interval end $intervalEnd:" +
                    " ${candleToString(finalCandle)}"
            )
            // **FIX:** Output with the context's timestamp (triggering element's timestamp)
            context.outputWithTimestamp(KV.of(key, finalCandle), context.timestamp())
            lastCandleState.write(finalCandle) // Update last *outputted* candle state
        }

        // Helper to output candle from timer context
        private fun outputCandleFromTimerContext(
            context: OnTimerContext, // Specific type needed for context
            candle: Candle,
            intervalEnd: Instant, // Not nullable here
            lastCandleState: ValueState<Candle>
        ) {
            if (candle == Candle.getDefaultInstance()) {
                logger.atFine().log(
                    "Attempted to output default instance from timer at $intervalEnd, skipping."
                )
                return
            }

            // Get currency pair directly from the candle
            val currencyPair = candle.currencyPair

            // Set the candle timestamp to the interval end time
            val finalCandle =
                candle.toBuilder().setTimestamp(Timestamps.fromMillis(intervalEnd.millis)).build()

            logger.atInfo().log(
                "Outputting candle (timer) for currency pair $currencyPair at interval end $intervalEnd:" +
                    " ${candleToString(finalCandle)}"
            )
            // **FIX:** Output with the context's timestamp (timer's fire timestamp)
            context.outputWithTimestamp(KV.of(currencyPair, finalCandle), context.timestamp())
            lastCandleState.write(finalCandle) // Update last *outputted* candle state
        }

        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("trades") tradesState: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEndState: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>, // Add lastCandleState here
            @TimerId(INTERVAL_END_TIMER) intervalEndTimer: Timer // Use renamed timer ID
        ) {
            val kv = context.element()
            val key = kv.key
            val trade = kv.value
            val tradeTimestamp = context.timestamp() // Use element timestamp
            logger.atFine().log("Processing trade for key $key at $tradeTimestamp")

            var currentTrades = tradesState.read() ?: ArrayList()
            var intervalEnd = currentIntervalEndState.read()

            // Initialize state if first element for this key
            if (intervalEnd == null) {
                intervalEnd = getIntervalEnd(tradeTimestamp)
                logger.atInfo().log("Initializing state for key $key. First interval end: $intervalEnd")
                currentIntervalEndState.write(intervalEnd)
                // **FIX:** Set the first timer for the *end* of the current interval
                intervalEndTimer.set(intervalEnd)
                logger.atInfo().log(
                    "Set initial interval end timer for key $key to $intervalEnd"
                )
            }

            // If the trade belongs to a future interval, finalize the current one(s) by emitting
            // candles
            while (intervalEnd != null && (tradeTimestamp.isEqual(intervalEnd) ||
                    tradeTimestamp.isAfter(intervalEnd))
                ) {
                logger.atInfo().log(
                    "Trade at $tradeTimestamp is at or after current interval end $intervalEnd" +
                        " for key $key. Emitting previous candle."
                )
                // Emit candle for the completed interval
                val candleToEmit = buildOrFillCandle(currentTrades, lastCandleState) // Pass state

                if (candleToEmit != null) {
                    outputCandleFromProcessContext(
                        context,
                        key,
                        candleToEmit,
                        intervalEnd,
                        lastCandleState
                    )
                } else {
                    logger.atWarning().log(
                        "No candle to emit for key $key at interval end $intervalEnd (no prior" +
                            " trades/state)."
                    )
                }

                // Clear trades for the completed interval
                currentTrades.clear()
                // Do NOT write the empty list back immediately, wait until the next trade or timer

                // Move state to the next interval
                val nextIntervalEnd = intervalEnd.plus(candleInterval)
                currentIntervalEndState.write(nextIntervalEnd)
                intervalEnd = nextIntervalEnd // Update local variable for loop condition

                // **FIX:** Reset the timer for the *end* of the *new* interval
                intervalEndTimer.set(intervalEnd)
                logger.atInfo().log(
                    "Advanced to next interval for key $key. New end: $intervalEnd. Reset timer" +
                        " to $intervalEnd"
                )
            }

            // Add the current trade to the list for the current interval
            currentTrades.add(trade)
            tradesState.write(currentTrades) // Write state after adding the trade
            logger.atFine().log(
                "Added trade to buffer for key $key. Buffer size: ${currentTrades.size}"
            )
        }

        @OnTimer(INTERVAL_END_TIMER)
        fun onTimer(
            context: OnTimerContext, // Correct type for @OnTimer
            @StateId("trades") tradesState: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEndState: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>,
            @TimerId(INTERVAL_END_TIMER) intervalEndTimer: Timer
        ) {
            val timerFireTimestamp = context.timestamp()
            val intervalEnd = currentIntervalEndState.read()
            val lastCandle = lastCandleState.read()

            // If state is missing or timer is for an old interval, ignore
            if (intervalEnd == null || !timerFireTimestamp.isEqual(intervalEnd)) {
                 logger.atWarning().log(
                     "Ignoring timer fired at %s. Expected interval end: %s. State might be missing or timer is late/early.",
                     timerFireTimestamp, intervalEnd
                 )
                 return
            }

            // We need to determine the currency pair from the last candle or trades
             val key = lastCandle?.currencyPair ?: tradesState.read()?.firstOrNull()?.currencyPair
             if (key == null) {
                 logger.atWarning().log("Timer fired at %s but cannot determine key (no last candle or trades in state). Skipping.", timerFireTimestamp)
                 return
             }


            logger.atInfo().log(
                "Timer fired for key %s at interval end %s. Last Output Candle: %s",
                key, timerFireTimestamp, candleToString(lastCandle)
            )

            // Timer fired at the correct interval end. Emit candle for this interval.
            val trades = tradesState.read() ?: ArrayList()
            val candleToEmit = buildOrFillCandle(trades, lastCandleState) // Attempt fill-forward

            if (candleToEmit != null) {
                // Output the candle for the interval that just ended
                outputCandleFromTimerContext(
                    context,
                    candleToEmit,
                    intervalEnd, // Use the interval end this timer represents
                    lastCandleState
                )
            } else {
                logger.atWarning().log(
                    "Timer fired for key %s at interval end %s, but no candle could be generated (no prior trades/state for fill-forward).",
                    key, intervalEnd
                )
            }

            // Clear trades for the emitted interval
            trades.clear()
            tradesState.write(trades) // Persist cleared trades list

            // Advance state to the next interval
            val nextIntervalEnd = intervalEnd.plus(candleInterval)
            currentIntervalEndState.write(nextIntervalEnd)

            // Set the timer for the *next* interval end
            intervalEndTimer.set(nextIntervalEnd)
            logger.atInfo().log(
                "Timer processed for key %s. Advanced interval end to %s. Set next timer for %s",
                key, nextIntervalEnd, nextIntervalEnd
            )
        }
    }
}
