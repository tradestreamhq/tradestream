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
 * Instead of using timers, this implementation detects gaps inline and immediately 
 * generates fill-forward candles when processing each new candle.
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

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Candle>,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>
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

        // Get the last output timestamp
        val lastOutputTimestamp = lastOutputTimestampState.read()
        
        // Check if we need to fill forward any gaps
        if (lastOutputTimestamp != null) {
            // Calculate expected next timestamp
            var nextExpectedTimestamp = lastOutputTimestamp.plus(intervalDuration)
            
            // If the actual candle comes after the expected next timestamp,
            // we need to fill in the gap with synthetic candles
            if (actualCandleTimestamp.isAfter(nextExpectedTimestamp)) {
                // Get the last actual candle for filling
                val lastActualCandle = lastActualCandleState.read()
                if (lastActualCandle != null) {
                    var fillCount = 0
                    
                    // Keep generating fill-forward candles until we reach the actual candle
                    // or hit the maximum fill limit
                    while (nextExpectedTimestamp.isBefore(actualCandleTimestamp) && 
                           fillCount < maxForwardIntervals) {
                        
                        logger.atInfo().log(
                            "Gap detected for key %s. Generating fill-forward candle at %s (interval %d of max %d)",
                            key,
                            nextExpectedTimestamp,
                            fillCount + 1,
                            maxForwardIntervals
                        )
                        
                        // Build and emit a fill-forward candle
                        val fillForwardCandle = buildFillForwardCandle(key, lastActualCandle, nextExpectedTimestamp)
                        context.output(KV.of(key, fillForwardCandle))
                        
                        logger.atInfo().log(
                            "Generated and outputted fill-forward for key %s at %s: %s",
                            key,
                            nextExpectedTimestamp,
                            candleToString(fillForwardCandle)
                        )
                        
                        // Update for next iteration
                        nextExpectedTimestamp = nextExpectedTimestamp.plus(intervalDuration)
                        fillCount++
                        
                        if (fillCount >= maxForwardIntervals) {
                            logger.atInfo().log(
                                "Reached maximum fill-forward limit (%d) for key %s",
                                maxForwardIntervals,
                                key
                            )
                            break
                        }
                    }
                }
            }
        }

        // Output the actual candle
        context.output(KV.of(key, actualCandle))
        logger.atInfo().log("Outputted actual candle for key %s at %s", key, actualCandleTimestamp)

        // Update state
        lastActualCandleState.write(actualCandle)
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

    /** Builds a fill-forward Candle protobuf message. */
    private fun buildFillForwardCandle(
        key: String,
        lastActualCandle: Candle,
        timestamp: Instant
    ): Candle {
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
        fun create(
            intervalDuration: Duration,
            maxForwardIntervals: Int = Int.MAX_VALUE
        ): FillForwardCandlesFn
    }
}
