package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.join.CoGbkResult
import org.apache.beam.sdk.transforms.join.CoGroupByKey
import org.apache.beam.sdk.transforms.join.KeyedPCollectionTuple
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.IntervalWindow
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.*
import org.joda.time.Duration
import org.joda.time.Instant
import java.util.function.Supplier
import com.google.protobuf.util.Timestamps
import com.google.protobuf.Timestamp // Ensure correct Timestamp import

/**
 * Transforms a stream of trades into OHLCV candles for a predefined list of currency pairs.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val windowDuration: Duration,
    @Assisted private val defaultPrice: Double,
    private val currencyPairsSupplier: Supplier<List<CurrencyPair>>,
    private val candleCreatorFn: CandleCreatorFn // Inject the DoFn directly
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>() {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val CANDLE_TAG = "candles"
        private const val IMPULSE_TAG = "impulses"

        // Updated to accept Instant directly
        fun createDefaultCandle(currencyPair: String, timestampInstant: Instant, defaultPrice: Double): Candle {
             logger.atFine().log("Creating default candle for %s at timestamp %s with price %.2f",
                 currencyPair, timestampInstant, defaultPrice)

             val builder = Candle.newBuilder()
                 .setOpen(defaultPrice)
                 .setHigh(defaultPrice)
                 .setLow(defaultPrice)
                 .setClose(defaultPrice)
                 .setVolume(0.0)
                 .setCurrencyPair(currencyPair)

             try {
                 // Attempt conversion using the provided Instant
                 builder.setTimestamp(Timestamps.fromMillis(timestampInstant.millis))
             } catch (e: IllegalArgumentException) {
                 // This catch might still be needed if the fallback Instant is somehow invalid
                 // for Timestamps, although less likely than Instant.MIN/MAX.
                 logger.atWarning().withCause(e).log(
                     "Failed to convert determined Instant to Timestamp: %s. Using EPOCH for %s",
                     timestampInstant, currencyPair
                 )
                 // Provide a guaranteed valid timestamp as ultimate fallback
                 builder.setTimestamp(Timestamp.newBuilder().setSeconds(0L).build()) // Use proto Timestamp builder for EPOCH
             }
             return builder.build()
         }
    }

    interface Factory {
        fun create(windowDuration: Duration, defaultPrice: Double): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log(
            "Starting TradeToCandle transform with window duration: %s, Default Price: %.2f",
            windowDuration, defaultPrice
        )
        val pipeline = input.pipeline

        val keyedTrades = input.apply("KeyByCurrencyPair",
            MapElements.into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Trade::class.java)))
                .via(SerializableFunction<Trade, KV<String, Trade>> { trade -> KV.of(trade.currencyPair, trade) })
        )

        val windowedTrades = keyedTrades.apply("WindowTrades",
            Window.into<KV<String, Trade>>(FixedWindows.of(windowDuration))
        )

        val actualCandles: PCollection<KV<String, Candle>> = windowedTrades
            .apply("AggregateCandles", ParDo.of(candleCreatorFn)) // Use injected instance
            .setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))

        val allKeys = currencyPairsSupplier.get().map { it.symbol() }
        if (allKeys.isEmpty()) {
            logger.atWarning().log("Currency pair supplier returned empty list. No default candles will be generated.")
            return actualCandles
        }

        // Create Impulse - elements will have timestamp Instant.MIN initially
        val impulse = pipeline
            .apply("CreateAllKeys", Create.of(allKeys))
            .apply("MapKeysToKV", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.booleans()))
                .via(SerializableFunction<String, KV<String, Boolean>> { key -> KV.of(key, true) })
            )
            // Apply windowing to the impulse - this assigns the IntervalWindow but doesn't change element timestamps
            .apply("WindowImpulses", Window.into<KV<String, Boolean>>(FixedWindows.of(windowDuration)))

        val candleTag = TupleTag<Candle>(CANDLE_TAG)
        val impulseTag = TupleTag<Boolean>(IMPULSE_TAG)

        val joined = KeyedPCollectionTuple.of(candleTag, actualCandles)
            .and(impulseTag, impulse)
            .apply("JoinCandlesWithImpulses", CoGroupByKey.create())

        // Updated DoFn to reliably determine timestamp for defaults
        val finalCandles = joined.apply("GenerateDefaults", ParDo.of(
            object : DoFn<KV<String, CoGbkResult>, KV<String, Candle>>() {
                @ProcessElement
                fun process(
                    @Element element: KV<String, CoGbkResult>,
                    context: ProcessContext,
                    window: BoundedWindow // Access window directly
                ) {
                    val currencyPair = element.key
                    val result = element.value
                    val candles = result.getAll(candleTag).toList()
                    val impulses = result.getAll(impulseTag).toList()

                    if (candles.isNotEmpty()) {
                        candles.forEach { candle ->
                            context.output(KV.of(currencyPair, candle))
                        }
                        logger.atFine().log("Output actual candle for %s in window %s", currencyPair, window)
                    } else if (impulses.isNotEmpty()) {
                        // *** FIX START ***
                        // Calculate timestamp *before* calling createDefaultCandle
                        var windowEndInstant: Instant? = null
                        var isTimestampValid = false
                        try {
                            // Prefer maxTimestamp as it's the intended trigger time
                            val maxTs = window.maxTimestamp()
                            // Basic sanity check (protobuf util handles detailed range check later)
                            if (maxTs != BoundedWindow.TIMESTAMP_MIN_VALUE && maxTs != BoundedWindow.TIMESTAMP_MAX_VALUE) {
                                windowEndInstant = maxTs
                                isTimestampValid = true
                                logger.atFine().log("Using window.maxTimestamp() for default: %s in window %s", windowEndInstant, window)
                            } else {
                                logger.atWarning().log("window.maxTimestamp() is MIN/MAX (%s) for window %s, attempting fallback.", maxTs, window)
                            }
                        } catch (e: Exception) {
                           // Catch any exception trying to access maxTimestamp
                           logger.atWarning().withCause(e).log("Error accessing window.maxTimestamp() for window %s, attempting fallback.", window)
                        }

                        if (!isTimestampValid) {
                            // Fallback: Use IntervalWindow.end() if possible
                            if (window is IntervalWindow) {
                                // IntervalWindow.end() is exclusive, maxTimestamp is inclusive end.
                                // So, end() - 1ms should equal maxTimestamp()
                                windowEndInstant = window.end().minus(Duration.millis(1))
                                isTimestampValid = true // Assume this is valid unless conversion fails later
                                logger.atInfo().log("Using fallback timestamp from IntervalWindow.end(): %s for window %s", windowEndInstant, window)
                            } else {
                                logger.atSevere().log(
                                    "Cannot determine valid window end timestamp for default candle for key %s in non-IntervalWindow %s. Skipping default.",
                                     currencyPair, window)
                                // Skip creating default candle if timestamp is indeterminable
                                return
                            }
                        }
                        // *** FIX END ***

                        // Ensure we determined a valid instant before proceeding
                        if (windowEndInstant == null) {
                             logger.atSevere().log(
                                 "Failed to determine a valid timestamp for default candle for key %s in window %s after fallback. Skipping default.",
                                 currencyPair, window)
                             return
                        }

                        try {
                            // Pass the determined Instant to createDefaultCandle
                            val defaultCandle = createDefaultCandle(currencyPair, windowEndInstant, defaultPrice)
                            context.output(KV.of(currencyPair, defaultCandle))
                            logger.atFine().log("Output default candle for %s at effective window end %s in window %s", currencyPair, windowEndInstant, window)
                        } catch (e: Exception) {
                            // Catch potential timestamp conversion error even from fallback
                            logger.atSevere().withCause(e).log(
                                "Failed to generate or output default candle for %s with determined timestamp %s in window %s",
                                currencyPair, windowEndInstant, window
                            )
                        }
                    } else {
                        // This case should ideally not happen with CoGroupByKey if impulse exists,
                        // but log defensively.
                        logger.atWarning().log(
                            "Unexpected CoGbkResult for key %s in window %s: No candles and no impulses.",
                            currencyPair, window
                        )
                    }
                }
            }
        )).setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))

        return finalCandles.setName("FinalCandlesWithDefaults")
    }
}
