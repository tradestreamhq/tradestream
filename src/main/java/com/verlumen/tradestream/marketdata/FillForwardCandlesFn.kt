package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
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
import java.io.Serializable

/**
 * Stateful DoFn to fill forward candle data.
 *
 * Takes KV<String, Candle> as input (output from an aggregation step).
 * Outputs KV<String, Candle> including original candles and generated fill-forward candles.
 * Assumes input candles arrive with timestamps corresponding to the *start* of their interval.
 * Fill-forward candles are emitted with timestamps corresponding to the *start* of the interval they fill.
 */
class FillForwardCandlesFn @Inject constructor(
    @Assisted private val intervalDuration: Duration // The expected duration between candles (e.g., 1 minute)
) : DoFn<KV<String, Candle>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L

        // Helper function for logging candle details
        private fun candleToString(candle: Candle?): String {
            if (candle == null) return "null"
            return "Candle{Pair:${candle.currencyPair}, T:${Timestamps.toString(candle.timestamp)}, " +
                    "O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
        }
    }

    // State to keep track of the last *actual* candle received for a key.
    @StateId("lastActualCandle")
    private val lastActualCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    // NEW State: Stores the timestamp of the last outputted candle (actual or fill-forward).
    @StateId("lastOutputTimestamp")
    private val lastOutputTimestampSpec: StateSpec<ValueState<Instant>> =
        StateSpecs.value(InstantCoder.of())

    // Timer to trigger checks for gaps. Set based on event time.
    @TimerId("gapCheckTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Candle>,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>, // Add new state
        @TimerId("gapCheckTimer") timer: Timer
    ) {
        val key = element.key
        val actualCandle = element.value
        val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))

        logger.atFine().log("Processing actual candle for key %s at %s: %s",
            key, actualCandleTimestamp, candleToString(actualCandle))

        // Output the actual candle received
        context.outputWithTimestamp(KV.of(key, actualCandle), actualCandleTimestamp)
        logger.atFine().log("Outputted actual candle for key %s at %s", key, actualCandleTimestamp)

        // Update state
        lastActualCandleState.write(actualCandle)
        lastOutputTimestampState.write(actualCandleTimestamp) // Update last output timestamp
        logger.atFine().log("Updated lastActualCandleState for key %s with actual candle at %s: %s",
             key, actualCandleTimestamp, candleToString(actualCandle))
        logger.atFine().log("Updated lastOutputTimestampState for key %s to %s", key, actualCandleTimestamp)

        // Set a timer for the next expected interval boundary
        val nextTimerInstant = actualCandleTimestamp.plus(intervalDuration)
        timer.set(nextTimerInstant)
        logger.atFine().log("Set timer for key %s at %s (after processing actual candle %s)",
             key, nextTimerInstant, actualCandleTimestamp)
    }

    @OnTimer("gapCheckTimer")
    fun onTimer(
        context: OnTimerContext,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>, // Add new state
        @TimerId("gapCheckTimer") timer: Timer
    ) {
        val timerTimestamp = context.timestamp()
        val lastActualCandle = lastActualCandleState.read()
        val lastOutputTimestamp = lastOutputTimestampState.read() ?: Instant.EPOCH // Default if null

        if (lastActualCandle == null) {
             logger.atWarning().log("Timer fired at %s but lastActualCandleState is null. Cannot fill forward.", timerTimestamp)
             return
        }

        val key = lastActualCandle.currencyPair

        logger.atFine().log("Timer fired for key %s at %s. Last actual candle timestamp: %s. Last output timestamp: %s",
            key, timerTimestamp, Instant(Timestamps.toMillis(lastActualCandle.timestamp)), lastOutputTimestamp)

        // ***MODIFIED CONDITION***
        // Check if this timer corresponds to the interval *immediately* following the last *outputted* element.
        if (timerTimestamp.isEqual(lastOutputTimestamp.plus(intervalDuration))) {
            logger.atFine().log("Gap confirmed for key %s at interval start %s (based on last output %s). Generating fill-forward.",
                key, timerTimestamp, lastOutputTimestamp)

            // Generate fill-forward using the last *actual* candle's close price
            val fillForwardCandle = buildFillForwardCandle(key, lastActualCandle, timerTimestamp)

            // Output the fill-forward candle
            context.outputWithTimestamp(KV.of(key, fillForwardCandle), timerTimestamp)
            logger.atFine().log("Generated and outputted fill-forward for key %s at %s: %s",
                key, timerTimestamp, candleToString(fillForwardCandle))

            // Update the last output timestamp state
            lastOutputTimestampState.write(timerTimestamp)
            logger.atFine().log("Updated lastOutputTimestampState for key %s to %s (after fill-forward)", key, timerTimestamp)

            // Set the timer for the next potential interval boundary
            val nextTimerInstant = timerTimestamp.plus(intervalDuration)
            timer.set(nextTimerInstant)
            logger.atFine().log("Set next timer for key %s at %s (after generating fill-forward for %s)",
                key, nextTimerInstant, timerTimestamp)
        } else {
             logger.atFine().log("Timer fired for key %s at %s, but it does not immediately follow the last output timestamp %s. Skipping fill-forward.",
                 key, timerTimestamp, lastOutputTimestamp)
             // This timer might be stale if a newer actual candle arrived or an earlier timer already filled this gap.
        }
    }

    /**
     * Builds a fill-forward Candle protobuf message.
     */
    private fun buildFillForwardCandle(key: String, lastActualCandle: Candle, timestamp: Instant): Candle {
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

    // Factory interface for Guice AssistedInject
    interface Factory {
        fun create(intervalDuration: Duration): FillForwardCandlesFn
    }
}
