package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
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
import java.io.Serializable

/**
 * Stateful DoFn to fill forward candle data using event time timers.
 */
class FillForwardCandlesFn
    @Inject
    constructor(
        @Assisted private val intervalDuration: Duration, // The expected duration between candles
        @Assisted private val maxForwardIntervals: Int = Int.MAX_VALUE, // Max intervals to fill
    ) : DoFn<KV<String, Candle>, KV<String, Candle>>(),
        Serializable {
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
            StateSpecs.value(
                org.apache.beam.sdk.coders.VarIntCoder
                    .of(),
            )

        // Timer: Used to schedule potential fill-forward generation
        @TimerId(FILL_FORWARD_TIMER)
        private val timerSpec: TimerSpec = TimerSpecs.timer(org.apache.beam.sdk.state.TimeDomain.EVENT_TIME)

        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
            @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
            @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>,
            @TimerId(FILL_FORWARD_TIMER) timer: Timer,
        ) {
            val key = context.element().key
            val actualCandle = context.element().value
            val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))

            logger.atInfo().log(
                "Processing actual candle for key %s at %s: %s",
                key,
                actualCandleTimestamp,
                candleToString(actualCandle),
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
                key,
                actualCandleTimestamp,
                candleToString(actualCandle),
            )
            logger.atInfo().log(
                "Updated lastOutputTimestampState for key %s to %s and reset fill count",
                key,
                actualCandleTimestamp,
            )

            // Set a timer for the end of the current interval to potentially generate a fill-forward candle.
            val nextTimerTimestamp = actualCandleTimestamp
            logger.atInfo().log("Setting timer for key %s at %s", key, nextTimerTimestamp)
            timer.set(nextTimerTimestamp)
        }

        @OnTimer(FILL_FORWARD_TIMER)
        fun onFillForwardTimer(
            context: OnTimerContext, // Correct type for @OnTimer
            @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
            @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
            @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>,
            @TimerId(FILL_FORWARD_TIMER) timer: Timer,
        ) {
            val timerTimestamp = context.timestamp()
            val lastActualCandle = lastActualCandleState.read()

            // If state is missing (e.g., expired), we cannot proceed.
            if (lastActualCandle == null) {
                logger.atWarning().log("Timer fired at %s but lastActualCandle state is missing. Skipping.", timerTimestamp)
                return
            }
            // The key is implicitly associated with the state and timer. Get it from the last candle.
            val key = lastActualCandle.currencyPair

            val lastOutputTimestamp = lastOutputTimestampState.read()
            var fillCount = fillForwardCountState.read() ?: 0

            logger.atInfo().log(
                "Timer fired for key %s at %s. LastOutput: %s, LastActual: %s, FillCount: %d",
                key,
                timerTimestamp,
                lastOutputTimestamp,
                candleToString(lastActualCandle),
                fillCount,
            )

            // Check if an actual candle arrived *after* this timer timestamp already.
            // If the lastOutputTimestamp is later than this timer's timestamp, it means newer data arrived, and the timer is obsolete.
            if (lastOutputTimestamp != null && lastOutputTimestamp.isAfter(timerTimestamp)) {
                logger.atInfo().log(
                    "Timer for key %s at %s is obsolete. Newer data already output at %s. Skipping.",
                    key,
                    timerTimestamp,
                    lastOutputTimestamp,
                )
                return // Do nothing, a newer actual candle covered this interval or state is missing/unexpected.
            }

            // Check if we've exceeded the max fill forward intervals.
            if (fillCount >= maxForwardIntervals) {
                logger.atInfo().log(
                    "Max fill-forward intervals (%d) reached for key %s at %s. Skipping.",
                    maxForwardIntervals,
                    key,
                    timerTimestamp,
                )
                return
            }

            // Ensure the timer is for the *next* expected interval after the last output.
            // If lastOutputTimestamp is null, this timer must be for the first candle, which shouldn't happen here.
            // If timerTimestamp is not equal to lastOutputTimestamp, something is off (e.g. late timer).
            if (lastOutputTimestamp == null || !timerTimestamp.isEqual(lastOutputTimestamp)) {
                logger.atWarning().log(
                    "Timer fired for key %s at %s, but last output timestamp was %s. Skipping potentially out-of-order timer.",
                    key,
                    timerTimestamp,
                    lastOutputTimestamp,
                )
                return
            }

            // Calculate the timestamp for the fill-forward candle.
            val fillForwardTimestamp = timerTimestamp.plus(intervalDuration)

            // Generate and output the fill-forward candle.
            val fillForwardCandle = buildFillForwardCandle(key, lastActualCandle, fillForwardTimestamp)
            // Output the candle using the TIMER'S timestamp to satisfy Beam's check.
            // This signifies the candle represents the state valid *up to* the timerTimestamp.
            context.outputWithTimestamp(KV.of(key, fillForwardCandle), timerTimestamp)
            logger.atInfo().log(
                "Generated and outputted fill-forward candle for key %s at %s: %s (Fill count %d/%d)",
                key,
                fillForwardTimestamp,
                candleToString(fillForwardCandle),
                fillCount + 1,
                maxForwardIntervals,
            )

            // Update state for the generated fill-forward candle.
            lastOutputTimestampState.write(fillForwardTimestamp) // Use the timestamp of the generated candle
            fillForwardCountState.write(++fillCount)

            logger.atInfo().log(
                "Updated lastOutputTimestampState for key %s to %s (fill-forward), incremented fill count to %d",
                key,
                fillForwardTimestamp,
                fillCount,
            )

            // Set the timer for the next interval if we haven't reached the limit.
            if (fillCount < maxForwardIntervals) {
                val nextTimerTimestamp = fillForwardTimestamp // Set next timer relative to the filled candle's time
                logger.atInfo().log("Setting next timer for key %s at %s", key, nextTimerTimestamp)
                timer.set(nextTimerTimestamp)
            } else {
                logger.atInfo().log(
                    "Reached max fill-forward intervals (%d) for key %s after generating candle at %s. Not setting further timers.",
                    maxForwardIntervals,
                    key,
                    fillForwardTimestamp,
                )
            }
        }

        /** Builds a fill-forward Candle protobuf message. */
        private fun buildFillForwardCandle(
            key: String,
            lastActualCandle: Candle,
            timestamp: Instant,
        ): Candle =
            Candle
                .newBuilder()
                .setCurrencyPair(key)
                .setTimestamp(Timestamps.fromMillis(timestamp.millis))
                .setOpen(lastActualCandle.close) // Use last actual close price
                .setHigh(lastActualCandle.close)
                .setLow(lastActualCandle.close)
                .setClose(lastActualCandle.close)
                .setVolume(0.0) // Zero volume for fill-forward
                .build()

        // Factory interface for Guice AssistedInject
        interface Factory {
            fun create(
                intervalDuration: Duration,
                maxForwardIntervals: Int = Int.MAX_VALUE,
            ): FillForwardCandlesFn
        }
    }
