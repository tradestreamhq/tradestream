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
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.OnTimer
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.TimerId
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.joda.time.Instant

/**
 * Stateful DoFn to fill forward candle data using event time timers.
 */
class FillForwardCandlesFn
@Inject
constructor(
    @Assisted private val intervalDuration: Duration, // The expected duration between candles
    @Assisted private val maxForwardIntervals: Int = Int.MAX_VALUE // Max intervals to fill
) : DoFn<KV<String, Candle>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 2L // Increment version due to logic change
        private const val FILL_FORWARD_TIMER = "fillForwardTimer"

        // Helper function for logging candle details
        private fun candleToString(candle: Candle?): String {
            if (candle == null) return "null"
            return "Candle{Pair=${candle.currencyPair}, " +
                    "T=${Timestamps.toString(candle.timestamp)}, " +
                    "O=${candle.open}, H=${candle.high}, L=${candle.low}, " +
                    "C=${candle.close}, V=${candle.volume}}"
        }
    }

    // State: Last actual candle received
    @StateId("lastActualCandle")
    private val lastActualCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    // State: Timestamp of the last outputted candle (actual or fill-forward)
    @StateId("lastOutputTimestamp")
    private val lastOutputTimestampSpec: StateSpec<ValueState<Instant>> =
        StateSpecs.value(InstantCoder.of())

    // State: Count of consecutive fill-forward candles generated
    @StateId("fillForwardCount")
    private val fillForwardCountSpec: StateSpec<ValueState<Int>> =
        StateSpecs.value(org.apache.beam.sdk.coders.VarIntCoder.of())

    // Timer: Used to schedule potential fill-forward generation
    @TimerId(FILL_FORWARD_TIMER)
    private val timerSpec: TimerSpec = TimerSpecs.timer(org.apache.beam.sdk.state.TimeDomain.EVENT_TIME)

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>,
        @TimerId(FILL_FORWARD_TIMER) timer: Timer
    ) {
        val key = context.element().key
        val actualCandle = context.element().value
        val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))

        logger.atInfo().log(
            "Processing actual candle for key %s at %s: %s",
            key, actualCandleTimestamp, candleToString(actualCandle)
        )

        // Output the actual candle received.
        context.outputWithTimestamp(KV.of(key, actualCandle), actualCandleTimestamp)
        logger.atInfo().log("Outputted actual candle for key %s at %s", key, actualCandleTimestamp)

        // Update state with the new actual candle.
        lastActualCandleState.write(actualCandle)
        lastOutputTimestampState.write(actualCandleTimestamp)
        fillForwardCountState.write(0) // Reset fill count as we received actual data.

        logger.atInfo().log(
            "Updated lastActualCandleState for key %s with actual candle at %s: %s",
            key, actualCandleTimestamp, candleToString(actualCandle)
        )
        logger.atInfo().log(
            "Updated lastOutputTimestampState for key %s to %s and reset fill count",
            key, actualCandleTimestamp
        )

        // Set a timer for the next expected interval to potentially generate a fill-forward candle.
        val nextTimerTimestamp = actualCandleTimestamp.plus(intervalDuration)
        logger.atInfo().log("Setting timer for key %s at %s", key, nextTimerTimestamp)
        timer.set(nextTimerTimestamp)
    }

    @OnTimer(FILL_FORWARD_TIMER)
    fun onFillForwardTimer(
        context: ProcessContext,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>,
        @TimerId(FILL_FORWARD_TIMER) timer: Timer
    ) {
        val key = context.key()
        val timerTimestamp = context.timestamp()

        val lastActualCandle = lastActualCandleState.read()
        val lastOutputTimestamp = lastOutputTimestampState.read()
        var fillCount = fillForwardCountState.read() ?: 0

        logger.atInfo().log(
            "Timer fired for key %s at %s. LastOutput: %s, LastActual: %s, FillCount: %d",
            key, timerTimestamp, lastOutputTimestamp, candleToString(lastActualCandle), fillCount
        )

        // Check if an actual candle arrived at or after this timer timestamp already.
        if (lastActualCandle == null || lastOutputTimestamp == null || !timerTimestamp.isAfter(lastOutputTimestamp)) {
            logger.atInfo().log(
                "Timer for key %s at %s is obsolete or state is missing. LastOutput: %s. Skipping.",
                 key, timerTimestamp, lastOutputTimestamp
            )
            return // Do nothing, an actual candle covered this interval or state is gone.
        }

        // Check if we've exceeded the max fill forward intervals.
        if (fillCount >= maxForwardIntervals) {
             logger.atInfo().log(
                "Max fill-forward intervals (%d) reached for key %s at %s. Skipping.",
                 maxForwardIntervals, key, timerTimestamp
            )
            return
        }

        // Ensure the timer is for the *next* expected interval after the last output.
        // This prevents duplicate fills if timers fire out of order (though unlikely with event time).
        val expectedTimerTimestamp = lastOutputTimestamp.plus(intervalDuration)
        if (!timerTimestamp.isEqual(expectedTimerTimestamp)) {
            logger.atWarning().log(
                "Timer fired for key %s at %s, but expected timer was for %s based on last output %s. Skipping.",
                key, timerTimestamp, expectedTimerTimestamp, lastOutputTimestamp
            )
            // We could potentially set a new timer for the *correct* expected timestamp here,
            // but for simplicity, we'll just let the next actual candle handle it.
            return
        }


        // Generate and output the fill-forward candle.
        val fillForwardCandle = buildFillForwardCandle(key, lastActualCandle, timerTimestamp)
        context.outputWithTimestamp(KV.of(key, fillForwardCandle), timerTimestamp)
        logger.atInfo().log(
            "Generated and outputted fill-forward candle for key %s at %s: %s (Fill count %d/%d)",
            key, timerTimestamp, candleToString(fillForwardCandle), fillCount + 1, maxForwardIntervals
        )

        // Update state for the generated fill-forward candle.
        lastOutputTimestampState.write(timerTimestamp)
        fillForwardCountState.write(++fillCount)

        logger.atInfo().log(
            "Updated lastOutputTimestampState for key %s to %s (fill-forward), incremented fill count to %d",
            key, timerTimestamp, fillCount
        )

        // Set the timer for the next interval if we haven't reached the limit.
        if (fillCount < maxForwardIntervals) {
            val nextTimerTimestamp = timerTimestamp.plus(intervalDuration)
            logger.atInfo().log("Setting next timer for key %s at %s", key, nextTimerTimestamp)
            timer.set(nextTimerTimestamp)
        } else {
             logger.atInfo().log(
                "Reached max fill-forward intervals (%d) for key %s after generating candle at %s. Not setting further timers.",
                 maxForwardIntervals, key, timerTimestamp
            )
        }
    }

    /** Builds a fill-forward Candle protobuf message. */
    private fun buildFillForwardCandle(
        key: String,
        lastActualCandle: Candle,
        timestamp: Instant
    ): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .setOpen(lastActualCandle.close) // Use last actual close price
            .setHigh(lastActualCandle.close)
            .setLow(lastActualCandle.close)
            .setClose(lastActualCandle.close)
            .setVolume(0.0) // Zero volume for fill-forward
            .build()
    }

    // Factory interface for Guice AssistedInject
    interface Factory {
        fun create(
            intervalDuration: Duration,
            maxForwardIntervals: Int = Int.MAX_VALUE
        ): FillForwardCandlesFn
    }
}
