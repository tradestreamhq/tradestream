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
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.joda.time.Instant

/**
 * Stateful DoFn to fill forward candle data.
 *
 * This implementation uses the element timestamp and window information
 * to detect and fill gaps in the candle stream.
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
    
    // State: Keeps track of how many fill-forward candles we've generated since the last actual candle
    @StateId("fillForwardCount")
    private val fillForwardCountSpec: StateSpec<ValueState<Int>> =
        StateSpecs.value(org.apache.beam.sdk.coders.VarIntCoder.of())

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Candle>,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>
    ) {
        val key = element.key
        val actualCandle = element.value
        val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))
        val elementTimestamp = context.timestamp()

        logger.atInfo().log(
            "Processing actual candle for key %s at %s: %s, element timestamp: %s",
            key,
            actualCandleTimestamp,
            candleToString(actualCandle),
            elementTimestamp
        )

        // Get the last actual candle and output timestamp (if any)
        val lastActualCandle = lastActualCandleState.read()
        var lastOutputTimestamp = lastOutputTimestampState.read() ?: Instant.EPOCH // Initialize if null

        // Reset fill-forward count since we have a real candle
        fillForwardCountState.write(0)

        // Timestamp to track the latest output in this processing step
        var latestOutputTimestampInStep = lastOutputTimestamp

        // Detect and fill forward any gaps if we have previous data
        if (lastActualCandle != null && lastOutputTimestamp != Instant.EPOCH) {
            // Check for gaps between the last output candle and the current actual candle first.
            var nextExpectedTimestamp = lastOutputTimestamp.plus(intervalDuration)
            if (actualCandleTimestamp.isAfter(nextExpectedTimestamp)) {
                latestOutputTimestampInStep = generateFillForwardBetweenCandles(
                    context,
                    key,
                    lastActualCandle,
                    lastOutputTimestamp, // Pass the state value directly
                    actualCandleTimestamp,
                    fillForwardCountState
                )
                // Update lastOutputTimestamp for the next check based on the result of filling
                lastOutputTimestamp = latestOutputTimestampInStep
            }

            // Then, check if we need to fill forward based on watermark/element timestamp advancement.
            // This handles scenarios where the pipeline progresses without new data.
            // Use >= to potentially generate a candle right at the element timestamp if needed
            if (elementTimestamp.isAfter(lastOutputTimestamp.plus(intervalDuration.multipliedBy(2)))) {
                latestOutputTimestampInStep = generateFillForwardBasedOnElementTimestamp(
                    context,
                    key,
                    lastActualCandle,
                    lastOutputTimestamp, // Pass the potentially updated lastOutputTimestamp
                    elementTimestamp,
                    fillForwardCountState
                )
                // Update lastOutputTimestamp based on the result of this filling step
                lastOutputTimestamp = latestOutputTimestampInStep
            }
        }

        // Output the actual candle
        context.output(KV.of(key, actualCandle))
        logger.atInfo().log("Outputted actual candle for key %s at %s", key, actualCandleTimestamp)

        // Update state with the current actual candle info
        lastActualCandleState.write(actualCandle)
        // Update last output timestamp state with the *actual* candle's timestamp,
        // as it's the latest event we've processed and outputted.
        lastOutputTimestampState.write(actualCandleTimestamp)

        logger.atInfo().log(
            "Updated lastActualCandleState for key %s with actual candle at %s: %s",
            key,
            actualCandleTimestamp,
            candleToString(actualCandle)
        )
        logger.atInfo().log(
            "Updated lastOutputTimestampState for key %s to %s",
            key,
            actualCandleTimestamp
        )
    }
    
    /**
     * Generates fill-forward candles based on element timestamp advancement.
     * This is used to fill forward when the watermark advances significantly without new data.
     * Returns the timestamp of the last generated fill-forward candle, or the initial lastOutputTimestamp if none generated.
     */
    private fun generateFillForwardBasedOnElementTimestamp(
        context: ProcessContext,
        key: String,
        lastActualCandle: Candle,
        initialLastOutputTimestamp: Instant, // Timestamp before this fill loop started
        currentElementTimestamp: Instant,
        fillForwardCountState: ValueState<Int>
    ): Instant { // Return the timestamp of the last generated candle
        logger.atInfo().log(
            "Generating fill-forward candles based on element timestamp for key %s from %s up to %s",
            key,
            initialLastOutputTimestamp,
            currentElementTimestamp
        )

        var fillCount = fillForwardCountState.read() ?: 0
        var nextTimestamp = initialLastOutputTimestamp.plus(intervalDuration)
        var lastGeneratedTimestamp = initialLastOutputTimestamp // Track the last *generated* timestamp

        // Generate fill-forward candles until we reach the max count or current element timestamp
        while (nextTimestamp.isBefore(currentElementTimestamp) && fillCount < maxForwardIntervals) {
            logger.atInfo().log(
                "Generating fill-forward candle for key %s at %s (count %d/%d, type: element_timestamp)",
                key,
                nextTimestamp,
                fillCount + 1,
                maxForwardIntervals
            )
            
            val fillForwardCandle = buildFillForwardCandle(
                key,
                lastActualCandle,
                nextTimestamp
            )

            context.outputWithTimestamp(KV.of(key, fillForwardCandle), nextTimestamp)
            lastGeneratedTimestamp = nextTimestamp // Update the timestamp of the last generated candle

            logger.atInfo().log(
                "Generated and outputted fill-forward candle for key %s at %s: %s",
                key,
                nextTimestamp,
                candleToString(fillForwardCandle)
            )

            nextTimestamp = nextTimestamp.plus(intervalDuration)
            fillCount++
        }

        fillForwardCountState.write(fillCount)

        logger.atInfo().log(
            "Finished generating fill-forward (element timestamp). Updated count for key %s to %d/%d. Last generated timestamp %s",
            key,
            fillCount,
            maxForwardIntervals,
            lastGeneratedTimestamp
        )
        return lastGeneratedTimestamp // Return the timestamp of the last generated candle
    }
    
    /**
     * Generates fill-forward candles between two actual candles.
     * Returns the timestamp of the last generated fill-forward candle, or the initial lastOutputTimestamp if none generated.
     */
    private fun generateFillForwardBetweenCandles(
        context: ProcessContext,
        key: String,
        lastActualCandle: Candle,
        initialLastOutputTimestamp: Instant, // Timestamp of the last output (actual or filled)
        currentActualCandleTimestamp: Instant, // Timestamp of the current actual candle
        fillForwardCountState: ValueState<Int>
    ): Instant { // Return the timestamp of the last generated candle
        logger.atInfo().log(
            "Generating fill-forward candles between actual candles for key %s from %s to %s",
            key,
            initialLastOutputTimestamp,
            currentActualCandleTimestamp
        )

        var fillCount = fillForwardCountState.read() ?: 0
        var nextTimestamp = initialLastOutputTimestamp.plus(intervalDuration)
        var lastGeneratedTimestamp = initialLastOutputTimestamp // Track the last *generated* timestamp in this loop

        // Generate fill-forward candles until we reach the current actual candle's timestamp or max count
        while (nextTimestamp.isBefore(currentActualCandleTimestamp) && fillCount < maxForwardIntervals) {
            logger.atInfo().log(
                "Generating fill-forward candle between candles for key %s at %s (count %d/%d, type: between_candles)",
                key,
                nextTimestamp,
                fillCount + 1,
                maxForwardIntervals
            )
            
            val fillForwardCandle = buildFillForwardCandle(
                key,
                lastActualCandle,
                nextTimestamp
            )

            context.outputWithTimestamp(KV.of(key, fillForwardCandle), nextTimestamp)
            lastGeneratedTimestamp = nextTimestamp // Update last generated time

            logger.atInfo().log(
                "Generated and outputted fill-forward candle for key %s at %s: %s",
                key,
                nextTimestamp,
                candleToString(fillForwardCandle)
            )

            nextTimestamp = nextTimestamp.plus(intervalDuration)
            fillCount++
        }

        fillForwardCountState.write(fillCount)

        logger.atInfo().log(
            "Finished generating fill-forward (between candles). Updated count for key %s to %d/%d. Last generated timestamp %s",
            key,
            fillCount,
            maxForwardIntervals,
            lastGeneratedTimestamp
        )
        return lastGeneratedTimestamp // Return the timestamp of the last generated candle
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
