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

/**
 * Transforms a stream of trades into OHLCV candles for a predefined list of currency pairs.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val windowDuration: Duration,
    @Assisted private val defaultPrice: Double,
    private val currencyPairsSupplier: Supplier<List<CurrencyPair>>,
    private val candleCreatorFn: CandleCreatorFn // Inject the aggregator DoFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>() {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val CANDLE_TAG = "candles"
        private const val IMPULSE_TAG = "impulses"

        // Updated to accept an Instant
        fun createDefaultCandle(currencyPair: String, timestampInstant: Instant, defaultPrice: Double): Candle {
            logger.atFine().log("Creating default candle for %s at timestamp %s with price %.2f",
                currencyPair, timestampInstant, defaultPrice)

            // Create the basic candle builder
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
                    "Failed to convert potentially valid Instant to Timestamp: %s. Using EPOCH for %s",
                    timestampInstant, currencyPair
                )
                // Provide a guaranteed valid timestamp as ultimate fallback
                builder.setTimestamp(Timestamps.EPOCH) // Use EPOCH instead of a potentially invalid calculated default
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

        // Use the injected CandleCreatorFn instance
        val actualCandles: PCollection<KV<String, Candle>> = windowedTrades
            .apply("AggregateCandles", ParDo.of(candleCreatorFn))
            .setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))


        val allKeys = currencyPairsSupplier.get().map { it.symbol() }
        if (allKeys.isEmpty()) {
            logger.atWarning().log("Currency pair supplier returned empty list. No default candles will be generated.")
            return actualCandles // Return only actual candles if no keys are expected
        }

        // Create impulse - Note: Timestamps default to Instant.MIN here, which might be problematic
        // if not handled carefully downstream, especially regarding window determination.
        val impulse = pipeline
            .apply("CreateAllKeys", Create.of(allKeys))
            .apply("MapKeysToKV", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.booleans()))
                .via(SerializableFunction<String, KV<String, Boolean>> { key -> KV.of(key, true) })
            )
            // Apply the same windowing to the impulse stream
            .apply("WindowImpulses", Window.into<KV<String, Boolean>>(FixedWindows.of(windowDuration)))


        val candleTag = TupleTag<Candle>(CANDLE_TAG)
        val impulseTag = TupleTag<Boolean>(IMPULSE_TAG)

        val joined = KeyedPCollectionTuple.of(candleTag, actualCandles)
            .and(impulseTag, impulse)
            .apply("JoinCandlesWithImpulses", CoGroupByKey.create())

        // Updated DoFn to handle timestamp calculation robustly
        val finalCandles = joined.apply("GenerateDefaults", ParDo.of(
            object : DoFn<KV<String, CoGbkResult>, KV<String, Candle>>() {
                @ProcessElement
                fun process(
                    @Element element: KV<String, CoGbkResult>,
                    context: ProcessContext,
                    window: BoundedWindow // Make window accessible
                ) {
                    val currencyPair = element.key
                    val result = element.value
                    val candles = result.getAll(candleTag).toList()
                    val impulses = result.getAll(impulseTag).toList()

                    if (candles.isNotEmpty()) {
                        candles.forEach { candle ->
                            context.output(KV.of(currencyPair, candle))
                        }
                        logger.atFine().log("Output actual candle for %s", currencyPair)
                    } else if (impulses.isNotEmpty()) {
                        // Generate default candle only if impulse exists and no actual candle exists
                        var windowEndInstant: Instant? = null
                        try {
                            // Prefer maxTimestamp as it's the intended trigger/end time for the window
                            windowEndInstant = window.maxTimestamp()
                            // Basic check for Beam's MIN/MAX sentinel values
                             if (windowEndInstant.millis <= Timestamps.MIN_VALUE.seconds * 1000 ||
                                 windowEndInstant.millis >= Timestamps.MAX_VALUE.seconds * 1000) {
                                 // Consider these invalid for our purpose, force fallback
                                 throw IllegalArgumentException("Window maxTimestamp is MIN/MAX or outside Protobuf range")
                             }
                             // Attempt conversion here to catch Protobuf range issues early
                             Timestamps.fromMillis(windowEndInstant.millis)
                             logger.atFinest().log("Using window.maxTimestamp() for default: %s", windowEndInstant)

                        } catch (e: Exception) {
                            logger.atWarning().log("window.maxTimestamp() is invalid or caused exception (%s). Attempting fallback using IntervalWindow for key %s.", e.message, currencyPair)
                            if (window is IntervalWindow) {
                                // IntervalWindow.end() is exclusive upper bound.
                                // BoundedWindow.maxTimestamp() is inclusive upper bound.
                                // So, end() - 1ms should ideally equal maxTimestamp(). Use this as fallback.
                                windowEndInstant = window.end().minus(Duration.millis(1))
                                logger.atFine().log("Fallback timestamp from IntervalWindow.end() - 1ms: %s", windowEndInstant)
                            } else {
                                logger.atSevere().log("Cannot determine window end timestamp for default candle for key %s in non-IntervalWindow %s", currencyPair, window)
                                // Skip creating default candle if timestamp is indeterminable
                                return
                            }
                        }

                        // Ensure we have a valid instant before proceeding
                        if (windowEndInstant == null) {
                             logger.atSevere().log("Failed to determine a valid timestamp for default candle for key %s", currencyPair)
                             return
                        }

                        try {
                            // Pass the determined Instant to createDefaultCandle
                            val defaultCandle = createDefaultCandle(currencyPair, windowEndInstant, defaultPrice)
                            context.output(KV.of(currencyPair, defaultCandle))
                            logger.atFine().log("Output default candle for %s at effective window end %s", currencyPair, windowEndInstant)
                        } catch (e: Exception) {
                            // Catch potential timestamp conversion error even from fallback logic
                            logger.atSevere().withCause(e).log(
                                "Failed to generate or output default candle for %s with calculated timestamp %s",
                                currencyPair, windowEndInstant
                            )
                        }
                    } else {
                        // This case (no candles, no impulses) shouldn't happen with CoGroupByKey
                        // if the impulse side covers all keys, but log if it does.
                        logger.atWarning().log(
                            "Unexpected CoGbkResult for key %s: No candles and no impulses.",
                            currencyPair
                        )
                    }
                }
            }
        )).setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))


        return finalCandles.setName("FinalCandlesWithDefaults")
    }
}
