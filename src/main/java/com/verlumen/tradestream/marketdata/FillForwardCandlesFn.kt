package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
import java.io.Serializable
import org.apache.beam.sdk.coders.InstantCoder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.joda.time.Instant

/**
 * Stateful DoFn to fill forward candle data.
 *
 * Takes KV<String, Candle> as input (output from an aggregation step). Outputs KV<String, Candle>
 * including original candles and generated fill-forward candles. Assumes input candles arrive with
 * timestamps corresponding to the *start* of their interval. Fill-forward candles are emitted with
 * timestamps corresponding to the *start* of the interval they fill.
 */
class FillForwardCandlesFn
@Inject
constructor(
    @Assisted private val intervalDuration: Duration, // The expected duration between candles (e.g., 1 minute)
    @Assisted private val maxForwardIntervals: Int = Int.MAX_VALUE // Maximum number of intervals to fill forward
) : DoFn<KV<String, Candle>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L

        // Helper function for logging candle details
        private fun candleToString(candle: Candle?): String {
            if (candle == null) return "null"
            // Using string templates for better readability, wrapped for length
            return "Candle{Pair=${candle.currencyPair}, " +
                "T=${Timestamps.toString(candle.timestamp)}, " +
                "O=${candle.open}, H=${candle.high}, L=${candle.low}, " +
                "C=${candle.close}, V=${candle.volume}}"
        }
    }

    // State to keep track of the last *actual* candle received for a key.
    @StateId("lastActualCandle")
    private val lastActualCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    // State: Stores the timestamp of the last outputted candle (actual or fill-forward).
    @StateId("lastOutputTimestamp")
    private val lastOutputTimestampSpec: StateSpec<ValueState<Instant>> =
        StateSpecs.value(InstantCoder.of())

    // State: Counter to track how many fill-forward intervals we've created
    @StateId("fillForwardCount")
    private val fillForwardCountSpec: StateSpec<ValueState<Int>> =
        StateSpecs.value(org.apache.beam.sdk.coders.VarIntCoder.of())

    // Timer to trigger checks for gaps. Set based on event time.
    @TimerId("gapCheckTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Candle>,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>,
        @TimerId("gapCheckTimer") timer: Timer
    ) {
        val key = element.key
        val actualCandle = element.value
        val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))

        logger.atInfo().log(
            "Processing actual candle for key %s at %s: %s",
            key,
            actualCandleTimestamp,
            candleToString(actualCandle)
        )

        // Output the actual candle received
        context.outputWithTimestamp(KV.of(key, actualCandle), actualCandleTimestamp)
        logger.atInfo().log("Outputted actual candle for key %s at %s", key, actualCandleTimestamp)

        // Update state
        lastActualCandleState.write(actualCandle)
        lastOutputTimestampState.write(actualCandleTimestamp) // Update last output timestamp

        // Reset the fill-forward counter since we got a new actual candle
        fillForwardCountState.write(0)

        logger.atInfo().log(
            "Updated lastActualCandleState for key %s with actual candle at %s: %s",
            key,
            actualCandleTimestamp,
            candleToString(actualCandle)
        )
        logger.atInfo().log(
            "Updated lastOutputTimestampState for key %s to %s", key, actualCandleTimestamp
        )
        logger.atInfo().log(
            "Reset fillForwardCount for key %s to 0", key
        )

        // Set a timer for the next expected interval boundary
        val nextTimerInstant = actualCandleTimestamp.plus(intervalDuration)
        // Set timer to fire at next interval, but associate its output time with the current element
        timer.withOutputTimestamp(actualCandleTimestamp).set(nextTimerInstant)
        logger.atInfo().log(
            "Set timer for key %s at %s (outputting at %s) (after processing actual candle %s)",
            key,
            nextTimerInstant,
            actualCandleTimestamp,
            actualCandleTimestamp
        )
    }

    @OnTimer("gapCheckTimer")
    fun onTimer(
        context: OnTimerContext,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>,
        @TimerId("gapCheckTimer") timer: Timer
    ) {
        val timerTimestamp = context.timestamp()
        val lastActualCandle = lastActualCandleState.read()
        // Use Elvis operator for default value, avoiding nullable Instant
        val lastOutputTimestamp = lastOutputTimestampState.read() ?: Instant.EPOCH
        // Get current fill-forward count, defaulting to 0 if not set
        val currentFillForwardCount = fillForwardCountState.read() ?: 0

        if (lastActualCandle == null) {
            logger.atWarning().log(
                "Timer fired at %s but lastActualCandleState is null. Cannot fill forward.",
                timerTimestamp
            )
            return // Early return requires braces if the block isn't empty
        }

        val key = lastActualCandle.currencyPair
        val lastActualTimestamp = Instant(Timestamps.toMillis(lastActualCandle.timestamp))

        logger.atInfo().log(
            "Timer fired for key %s at %s. Last actual candle timestamp: %s. Last output timestamp: %s. Current fill-forward count: %d/%d",
            key,
            timerTimestamp,
            lastActualTimestamp,
            lastOutputTimestamp,
            currentFillForwardCount,
            maxForwardIntervals
        )

        // Check if a fill-forward is needed and allowed
        // Breaking long line before logical operators
        // Added braces as per rule
        if (
            timerTimestamp.isAfter(lastActualTimestamp) && // Ensures we don't fill *over* the last actual data
            timerTimestamp.isEqual(lastOutputTimestamp.plus(intervalDuration)) && // Checks if this is the immediate next interval
            currentFillForwardCount < maxForwardIntervals // Strict check against the maximum allowed
        ) {
            logger.atInfo().log(
                "Gap confirmed for key %s at interval start %s. " +
                    "Generating fill-forward (interval %d of max %d).",
                key,
                timerTimestamp,
                currentFillForwardCount + 1,
                maxForwardIntervals
            )

            // Generate fill-forward using the last *actual* candle's close price
            val fillForwardCandle = buildFillForwardCandle(key, lastActualCandle, timerTimestamp)

            // Output the fill-forward candle
            context.outputWithTimestamp(KV.of(key, fillForwardCandle), timerTimestamp)
            logger.atInfo().log(
                "Generated and outputted fill-forward for key %s at %s: %s",
                key,
                timerTimestamp,
                candleToString(fillForwardCandle)
            )

            // Update the last output timestamp state
            lastOutputTimestampState.write(timerTimestamp)
            logger.atInfo().log(
                "Updated lastOutputTimestampState for key %s to %s (after fill-forward)",
                key,
                timerTimestamp
            )

            // Increment the fill-forward counter
            val newCount = currentFillForwardCount + 1
            fillForwardCountState.write(newCount)
            logger.atInfo().log(
                "Updated fillForwardCount for key %s to %d/%d",
                key,
                newCount,
                maxForwardIntervals
            )

            // Only set the timer for the next potential interval boundary if we haven't reached the max
            if (newCount < maxForwardIntervals) {
                val nextTimerInstant = timerTimestamp.plus(intervalDuration)
                // Set timer to fire at next interval, but associate its output time with the current timer's fire time
                timer.withOutputTimestamp(timerTimestamp).set(nextTimerInstant)
                logger.atInfo().log(
                    "Set next timer for key %s at %s (outputting at %s) (after generating fill-forward for %s)",
                    key,
                    nextTimerInstant,
                    timerTimestamp,
                    timerTimestamp
                 )
            } else {
                logger.atInfo().log(
                    "Reached maximum fill-forward limit (%d) for key %s. Not scheduling more timers.",
                    maxForwardIntervals,
                    key
                )
            }
        } else {
            // Provide detailed logging about why we're not filling forward
            val reasons = mutableListOf<String>()
            if (!timerTimestamp.isAfter(lastActualTimestamp)) {
                reasons.add("timer timestamp ${timerTimestamp} is not after last actual timestamp ${lastActualTimestamp}")
            }
            if (!timerTimestamp.isEqual(lastOutputTimestamp.plus(intervalDuration))) {
                reasons.add("timer timestamp ${timerTimestamp} is not the next expected interval after ${lastOutputTimestamp}")
            }
            if (currentFillForwardCount >= maxForwardIntervals) {
                reasons.add("reached maximum fill-forward count (${currentFillForwardCount}/${maxForwardIntervals})")
            }

            logger.atInfo().log(
                "Timer fired for key %s at %s, but not filling forward. Reasons: %s",
                key,
                timerTimestamp,
                reasons.joinToString(", ")
             )
        }
    }

    /** Builds a fill-forward Candle protobuf message. */
    private fun buildFillForwardCandle(
        key: String,
        lastActualCandle: Candle,
        timestamp: Instant
    ): Candle {
        // Using builder pattern with indentation
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .setOpen(lastActualCandle.close)
            .setHigh(lastActualCandle.close)
            .setLow(lastActualCandle.close)
            .setClose(lastActualCandle.close)
            .setVolume(0.0)
            .build()
    }

    /**
     * Allows timestamp skew when outputting elements.
     * Required to handle scenarios where processing time might cause elements
     * to be emitted slightly after their intended event time window boundary,
     * especially when dealing with timers.
     */
    override fun getAllowedTimestampSkew(): Duration = intervalDuration

    // Factory interface for Guice AssistedInject
    interface Factory {
        fun create(
            intervalDuration: Duration,
            maxForwardIntervals: Int = Int.MAX_VALUE
        ): FillForwardCandlesFn // Parameters on new lines for long signature
    }
}
