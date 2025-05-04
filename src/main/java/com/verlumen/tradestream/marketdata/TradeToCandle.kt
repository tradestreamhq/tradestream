package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.OnTimer
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.transforms.DoFn.TimerId
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TypeDescriptors
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.Serializable
import java.util.ArrayList
import com.google.protobuf.Timestamp as ProtoTimestamp
import com.google.protobuf.util.Timestamps

class TradeToCandle @Inject constructor(
    @Assisted private val candleInterval: Duration,
    private val candleCombineFn: CandleCombineFn // Keep CombineFn dependency
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 4L // Increment version due to logic change
    }

    interface Factory {
        fun create(candleInterval: Duration): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        val keyed: PCollection<KV<String, Trade>> = input // Explicit type for clarity
            .apply("KeyByPair", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.of(Trade::class.java))) // Corrected TypeDescriptors
                .via(SerializableFunction { t: Trade -> KV.of(t.currencyPair, t) }))
           // Removed incorrect setCoder call

        return keyed
            .apply("StatefulCandle", ParDo.of(StatefulTradeProcessor(candleInterval, candleCombineFn)))
           // Removed incorrect setCoder call
    }

    private class StatefulTradeProcessor(
        private val candleInterval: Duration,
        private val candleCombineFn: CandleCombineFn
    ) : DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID = 4L // Increment version due to logic change

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

        @TimerId("gapTimer")
        private val gapTimerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

        // Helper to get interval boundary
        private fun getIntervalEnd(timestamp: Instant): Instant {
            val ms = timestamp.millis
            val intervalMillis = candleInterval.millis
            // Calculate the end of the interval containing the timestamp
            return Instant((ms / intervalMillis) * intervalMillis + intervalMillis) // Corrected boundary calculation
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
                    logger.atFine().log("Filling forward using last candle: ${candleToString(lastActualCandle)}")
                    // Create a new candle based on the last actual one, but set volume to zero
                    // and keep OHLC the same (as last close)
                    lastActualCandle.toBuilder()
                        .setOpen(lastActualCandle.close)
                        .setHigh(lastActualCandle.close)
                        .setLow(lastActualCandle.close)
                        // Close price remains the same (lastActualCandle.close)
                        .setVolume(0.0) // Explicitly set volume to zero for fill-forward
                        // Timestamp will be set by the calling function (outputCandle...)
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
            lastCandleState: ValueState<Candle>) {

            if (candle == Candle.getDefaultInstance()) {
                logger.atFine().log("Attempted to output default instance for key $key at $intervalEnd, skipping.")
                return
            }

            // Set the candle timestamp to the interval end time
            val finalCandle = candle.toBuilder()
                .setTimestamp(Timestamps.fromMillis(intervalEnd.millis))
                .build()

            logger.atInfo().log("Outputting candle (process) for key $key at interval end $intervalEnd: ${candleToString(finalCandle)}")
            context.outputWithTimestamp(KV.of(key, finalCandle), intervalEnd)
            lastCandleState.write(finalCandle) // Update last *outputted* candle state
        }

        // Helper to output candle from timer context
        private fun outputCandleFromTimerContext(
            context: OnTimerContext, // Specific type needed for context.key()
            candle: Candle,
            intervalEnd: Instant, // Not nullable here
            lastCandleState: ValueState<Candle>) {

            if (candle == Candle.getDefaultInstance()) {
                 logger.atFine().log("Attempted to output default instance from timer for key ${context.key()} at $intervalEnd, skipping.")
                return
            }

            val key = context.key() // Correct way to get key in OnTimerContext
            // Set the candle timestamp to the interval end time
            val finalCandle = candle.toBuilder()
                .setTimestamp(Timestamps.fromMillis(intervalEnd.millis))
                .build()

             logger.atInfo().log("Outputting candle (timer) for key $key at interval end $intervalEnd: ${candleToString(finalCandle)}")
            context.outputWithTimestamp(KV.of(key, finalCandle), intervalEnd)
            lastCandleState.write(finalCandle) // Update last *outputted* candle state
        }


        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("trades") tradesState: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEndState: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>, // Add lastCandleState here
            @TimerId("gapTimer") gapTimer: Timer
        ) {
            val kv = context.element()
            val key = kv.key
            val trade = kv.value
            val tradeTimestamp = Instant(context.timestamp().millis) // Use element timestamp
            logger.atFine().log("Processing trade for key $key at $tradeTimestamp")


            var currentTrades = tradesState.read() ?: ArrayList()
            var intervalEnd = currentIntervalEndState.read()

            // Initialize state if first element for this key
            if (intervalEnd == null) {
                intervalEnd = getIntervalEnd(tradeTimestamp)
                logger.atInfo().log("Initializing state for key $key. First interval end: $intervalEnd")
                currentIntervalEndState.write(intervalEnd)
                // Set the first gap timer relative to the *end* of the interval containing the first trade
                 gapTimer.set(intervalEnd.plus(candleInterval)) // Set timer relative to interval end + candle duration
                logger.atInfo().log("Set initial gap timer for key $key to ${intervalEnd.plus(candleInterval)}")
            }

            // If the trade belongs to a future interval, finalize the current one(s) by emitting candles
            while (tradeTimestamp.isEqual(intervalEnd!!) || tradeTimestamp.isAfter(intervalEnd!!)) { // Use non-null assertion
                 logger.atInfo().log("Trade at $tradeTimestamp is at or after current interval end $intervalEnd for key $key. Emitting previous candle.")
                 // Emit candle for the completed interval
                 val candleToEmit = buildOrFillCandle(currentTrades, lastCandleState) // Pass state

                if (candleToEmit != null) {
                     outputCandleFromProcessContext(context, key, candleToEmit, intervalEnd!!, lastCandleState) // Use non-null assertion
                } else {
                     logger.atWarning().log("No candle to emit for key $key at interval end $intervalEnd (no prior trades/state).")
                }

                 // Clear trades for the completed interval
                 currentTrades.clear()
                 // Do NOT write the empty list back immediately, wait until the next trade or timer

                 // Move state to the next interval
                 val nextIntervalEnd = intervalEnd!!.plus(candleInterval) // Use non-null assertion
                 currentIntervalEndState.write(nextIntervalEnd)
                 intervalEnd = nextIntervalEnd // Update local variable for loop condition

                 // Reset the timer for the *new* interval end + grace period
                 gapTimer.set(intervalEnd.plus(candleInterval))
                 logger.atInfo().log("Advanced to next interval for key $key. New end: $intervalEnd. Reset timer to ${intervalEnd.plus(candleInterval)}")
            }

            // Add the current trade to the list for the current interval
            currentTrades.add(trade)
            tradesState.write(currentTrades) // Write state after adding the trade
            logger.atFine().log("Added trade to buffer for key $key. Buffer size: ${currentTrades.size}")

        }

        @OnTimer("gapTimer")
        fun onTimer(
             // Use fully qualified type for OnTimerContext
            context: DoFn<KV<String, Trade>, KV<String, Candle>>.OnTimerContext,
            @StateId("trades") tradesState: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEndState: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>,
            @TimerId("gapTimer") gapTimer: Timer
        ) {
            val timerFireTimestamp = context.timestamp()
            val key = context.key() // Get key from timer context
            val intervalEnd = currentIntervalEndState.read()

            logger.atInfo().log("Timer fired for key $key at $timerFireTimestamp. Expected interval end + duration: ${intervalEnd?.plus(candleInterval)}")

             // If state is missing or timer is for an old interval, ignore
             if (intervalEnd == null || !timerFireTimestamp.isEqual(intervalEnd.plus(candleInterval))) {
                 logger.atWarning().log("Ignoring timer for key $key at $timerFireTimestamp. Current IntervalEnd: $intervalEnd. Timer might be late, state missing, or for an already processed interval.")
                 return
            }

             // Emit candle for the interval that just ended (which might be empty -> fill-forward)
             val trades = tradesState.read() ?: ArrayList()
             val candleToEmit = buildOrFillCandle(trades, lastCandleState)

            if (candleToEmit != null) {
                // Output with the timestamp of the interval end the timer corresponds to
                 outputCandleFromTimerContext(context, candleToEmit, intervalEnd, lastCandleState) // Pass non-null intervalEnd
            } else {
                logger.atWarning().log("Timer fired for key $key at interval end $intervalEnd, but no candle to emit (no prior trades/state for fill-forward).")
            }

             // Clear trades for the emitted interval
             trades.clear()
             tradesState.write(trades) // Persist cleared trades list

             // Advance state to the next interval
             val nextIntervalEnd = intervalEnd.plus(candleInterval) // intervalEnd is non-null here
             currentIntervalEndState.write(nextIntervalEnd)

             // Set the timer for the *next* gap
             gapTimer.set(nextIntervalEnd.plus(candleInterval))
             logger.atInfo().log("Timer processed for key $key. Advanced interval end to $nextIntervalEnd. Set next timer for ${nextIntervalEnd.plus(candleInterval)}")
        }
    }
}
