package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
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

    // Timer to trigger checks for gaps. Set based on event time.
    @TimerId("gapCheckTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Candle>,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @TimerId("gapCheckTimer") timer: Timer
    ) {
        val key = element.key
        val actualCandle = element.value
        // Use the candle's own timestamp as its event time
        val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))

        logger.atFine().log("Processing actual candle for key %s at %s: %s",
            key, actualCandleTimestamp, candleToString(actualCandle))

        // --- Removed fill-forward logic from @ProcessElement ---
        // Gap filling is now handled exclusively by the @OnTimer callback.

        // Output the actual candle received, using its own timestamp
        context.outputWithTimestamp(KV.of(key, actualCandle), actualCandleTimestamp)

        // Update the state with the latest actual candle
        lastActualCandleState.write(actualCandle)
        logger.atFine().log("Updated lastActualCandleState for key %s with actual candle at %s: %s",
             key, actualCandleTimestamp, candleToString(actualCandle))

        // Set a timer for the *next* expected interval boundary *after* this actual candle
        // This timer will trigger the @OnTimer if no new actual candle arrives for that interval.
        val nextTimerInstant = actualCandleTimestamp.plus(intervalDuration)
        timer.set(nextTimerInstant)
        logger.atFine().log("Set timer for key %s at %s (after processing actual candle %s)",
             key, nextTimerInstant, actualCandleTimestamp)
    }

    @OnTimer("gapCheckTimer")
    fun onTimer(
        context: OnTimerContext,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @TimerId("gapCheckTimer") timer: Timer
    ) {
        val timerTimestamp = context.timestamp() // This is the timestamp the timer was set for (start of the expected interval)
        val lastActualCandle = lastActualCandleState.read()

        if (lastActualCandle == null) {
             logger.atWarning().log("Timer fired at %s but lastActualCandleState is null. Cannot fill forward.", timerTimestamp)
             return // Cannot fill forward without a previous candle
        }

        val key = lastActualCandle.currencyPair // Get key from the state
        val lastActualTimestamp = Instant(Timestamps.toMillis(lastActualCandle.timestamp))

        logger.atFine().log("Timer fired for key %s at %s. Last actual candle timestamp: %s",
            key, timerTimestamp, lastActualTimestamp)

        // Check if this timer corresponds to the interval *immediately* following the last *actual* candle.
        // If lastActualTimestamp + intervalDuration == timerTimestamp, it means no newer actual candle
        // arrived for the interval starting at timerTimestamp, confirming a gap.
        if (lastActualTimestamp.plus(intervalDuration).isEqual(timerTimestamp)) {
            logger.atFine().log("Gap confirmed for key %s at interval start %s. Generating fill-forward.",
                key, timerTimestamp)

            // Generate and output the fill-forward candle for the interval starting at timerTimestamp
            val fillForwardCandle = buildFillForwardCandle(key, lastActualCandle, timerTimestamp)
            // Output the fill-forward candle using the timer's timestamp (which is the start of the gap interval)
            context.outputWithTimestamp(KV.of(key, fillForwardCandle), timerTimestamp)
            logger.atFine().log("Generated fill-forward for key %s at %s: %s",
                key, timerTimestamp, candleToString(fillForwardCandle))

            // IMPORTANT: Do NOT update lastActualCandleState with the fill-forward candle.
            // The state should only reflect the last *actual* candle received.

            // Set the timer for the *next* potential interval boundary after the gap we just filled
            val nextTimerInstant = timerTimestamp.plus(intervalDuration)
            timer.set(nextTimerInstant)
            logger.atFine().log("Set next timer for key %s at %s (after generating fill-forward for %s)",
                key, nextTimerInstant, timerTimestamp)
        } else {
             // This timer is likely stale. Either:
             // 1. A newer actual candle arrived after this timer was set, but before it fired.
             //    That newer candle would have updated the state and set its own timer.
             // 2. An earlier timer already filled this gap (less likely with correct logic).
             logger.atFine().log("Timer fired for key %s at %s, but it's likely stale based on last actual candle timestamp %s. Skipping fill-forward.",
                 key, timerTimestamp, lastActualTimestamp)
        }
    }

    /**
     * Builds a fill-forward Candle protobuf message.
     * Uses the close price of the lastActualCandle and the timestamp of the interval start.
     */
    private fun buildFillForwardCandle(key: String, lastActualCandle: Candle, timestamp: Instant): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(key)
            .setTimestamp(Timestamps.fromMillis(timestamp.millis)) // Use the interval start timestamp
            .setOpen(lastActualCandle.close) // Fill forward using the last known close price
            .setHigh(lastActualCandle.close)
            .setLow(lastActualCandle.close)
            .setClose(lastActualCandle.close)
            .setVolume(0.0) // Zero volume indicates fill-forward
            .build()
    }

    // Factory interface for Guice AssistedInject
    interface Factory {
        fun create(intervalDuration: Duration): FillForwardCandlesFn
    }
}
