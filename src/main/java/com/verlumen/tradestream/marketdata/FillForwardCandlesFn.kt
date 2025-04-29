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
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.joda.time.Instant

/**
 * Stateful DoFn to fill forward candle data.
 *
 * This implementation uses both element processing and watermark advancement 
 * to generate fill-forward candles, ensuring gaps are filled even when
 * no new candles arrive for a period of time.
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
    
    // State: Keeps track of how many fill-forward candles we've generated
    @StateId("fillForwardCount")
    private val fillForwardCountSpec: StateSpec<ValueState<Int>> =
        StateSpecs.value(org.apache.beam.sdk.coders.VarIntCoder.of())

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        window: BoundedWindow,
        @Element element: KV<String, Candle>,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>
    ) {
        val key = element.key
        val actualCandle = element.value
        val actualCandleTimestamp = Instant(Timestamps.toMillis(actualCandle.timestamp))
        val watermarkTimestamp = context.currentWatermark()

        logger.atInfo().log(
            "Processing actual candle for key %s at %s: %s, current watermark: %s",
            key,
            actualCandleTimestamp,
            candleToString(actualCandle),
            watermarkTimestamp
        )

        // Reset fill-forward count since we received a real candle
        fillForwardCountState.write(0)
        
        // Get the last output timestamp
        val lastOutputTimestamp = lastOutputTimestampState.read()
        
        // Check if we need to fill forward any gaps from last candle to this one
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
                        context.outputWithTimestamp(KV.of(key, fillForwardCandle), nextExpectedTimestamp)
                        
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
                                "Reached maximum fill-forward limit (%d) for key %s when filling gap",
                                maxForwardIntervals,
                                key
                            )
                            break
                        }
                    }
                }
            }
        }

        // Output the actual candle with its timestamp
        context.outputWithTimestamp(KV.of(key, actualCandle), actualCandleTimestamp)
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
        
        // Handle watermark-based fill-forward after processing the real candle
        generateWatermarkBasedFillForward(
            context, 
            key, 
            actualCandle, 
            actualCandleTimestamp, 
            watermarkTimestamp, 
            fillForwardCountState
        )
    }
    
    /**
     * Called when the watermark advances, allowing us to generate fill-forward
     * candles even when no new actual candles arrive.
     */
    @OnWatermarkAdvance
    fun onWatermarkAdvance(
        context: OnWatermarkContext,
        @StateId("lastActualCandle") lastActualCandleState: ValueState<Candle>,
        @StateId("lastOutputTimestamp") lastOutputTimestampState: ValueState<Instant>,
        @StateId("fillForwardCount") fillForwardCountState: ValueState<Int>
    ) {
        val watermarkTimestamp = context.currentWatermark()
        logger.atInfo().log("Watermark advanced to %s", watermarkTimestamp)
        
        // Get the last actual candle and timestamp
        val lastActualCandle = lastActualCandleState.read() ?: return
        val lastOutputTimestamp = lastOutputTimestampState.read() ?: return
        
        // Get the current fill-forward count
        val currentFillForwardCount = fillForwardCountState.read() ?: 0
        
        // If we've already hit the maximum, don't generate more
        if (currentFillForwardCount >= maxForwardIntervals) {
            logger.atInfo().log(
                "Already reached maximum fill-forward count (%d/%d) for key %s",
                currentFillForwardCount,
                maxForwardIntervals,
                lastActualCandle.currencyPair
            )
            return
        }
        
        // Calculate the next expected timestamp
        val nextExpectedTimestamp = lastOutputTimestamp.plus(intervalDuration)
        
        // Only generate a fill-forward if the watermark has advanced enough
        if (watermarkTimestamp.isAfter(nextExpectedTimestamp)) {
            logger.atInfo().log(
                "Watermark advanced beyond next expected timestamp for key %s. " +
                "Generating fill-forward at %s (count %d/%d)",
                lastActualCandle.currencyPair,
                nextExpectedTimestamp,
                currentFillForwardCount + 1,
                maxForwardIntervals
            )
            
            // Build and emit the fill-forward candle
            val fillForwardCandle = buildFillForwardCandle(
                lastActualCandle.currencyPair, 
                lastActualCandle, 
                nextExpectedTimestamp
            )
            context.outputWithTimestamp(
                KV.of(lastActualCandle.currencyPair, fillForwardCandle), 
                nextExpectedTimestamp
            )
            
            // Update state
            lastOutputTimestampState.write(nextExpectedTimestamp)
            fillForwardCountState.write(currentFillForwardCount + 1)
            
            logger.atInfo().log(
                "Generated fill-forward candle at %s for key %s. Updated fill-forward count to %d/%d",
                nextExpectedTimestamp,
                lastActualCandle.currencyPair,
                currentFillForwardCount + 1,
                maxForwardIntervals
            )
        }
    }
    
    /**
     * Helper method to generate watermark-based fill-forward candles.
     */
    private fun generateWatermarkBasedFillForward(
        context: ProcessContext,
        key: String,
        actualCandle: Candle,
        actualCandleTimestamp: Instant,
        watermarkTimestamp: Instant,
        fillForwardCountState: ValueState<Int>
    ) {
        // Only proceed if there's a meaningful watermark
        if (watermarkTimestamp == null || watermarkTimestamp.isBefore(actualCandleTimestamp)) {
            return
        }
        
        logger.atInfo().log(
            "Checking for watermark-based fill-forward from %s to %s for key %s",
            actualCandleTimestamp,
            watermarkTimestamp,
            key
        )
        
        var nextExpectedTimestamp = actualCandleTimestamp.plus(intervalDuration)
        var fillCount = fillForwardCountState.read() ?: 0
        
        // Keep generating fill-forward candles until we reach the watermark timestamp
        // or hit our maximum limit
        while (nextExpectedTimestamp.isBefore(watermarkTimestamp) && fillCount < maxForwardIntervals) {
            logger.atInfo().log(
                "Watermark allows fill-forward for key %s at %s (count %d/%d)",
                key,
                nextExpectedTimestamp,
                fillCount + 1,
                maxForwardIntervals
            )
            
            // Build and emit a watermark-based fill-forward candle
            val fillForwardCandle = buildFillForwardCandle(key, actualCandle, nextExpectedTimestamp)
            context.outputWithTimestamp(KV.of(key, fillForwardCandle), nextExpectedTimestamp)
            
            logger.atInfo().log(
                "Generated and outputted watermark-based fill-forward for key %s at %s: %s",
                key,
                nextExpectedTimestamp,
                candleToString(fillForwardCandle)
            )
            
            // Update for next iteration
            nextExpectedTimestamp = nextExpectedTimestamp.plus(intervalDuration)
            fillCount++
            
            if (fillCount >= maxForwardIntervals) {
                logger.atInfo().log(
                    "Reached maximum fill-forward limit (%d) for key %s when performing watermark fill",
                    maxForwardIntervals,
                    key
                )
                break
            }
        }
        
        // Update the fill-forward count state
        fillForwardCountState.write(fillCount)
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
