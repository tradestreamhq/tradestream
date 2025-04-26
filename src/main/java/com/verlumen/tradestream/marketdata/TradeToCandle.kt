package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.join.CoGbkResult
import org.apache.beam.sdk.transforms.join.CoGroupByKey
import org.apache.beam.sdk.transforms.join.KeyedPCollectionTuple
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.IntervalWindow
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.*
import org.joda.time.Duration
import org.joda.time.Instant
import java.util.function.Supplier
import com.google.protobuf.util.Timestamps // For default candle timestamp

/**
 * Transforms a stream of trades into OHLCV candles for a predefined list of currency pairs.
 *
 * Ensures that a candle (either actual or default) is produced for every known
 * currency pair in every window.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val windowDuration: Duration,
    @Assisted private val defaultPrice: Double,
    private val currencyPairsSupplier: Supplier<List<CurrencyPair>>,
    // Inject the aggregator DoFn directly, assuming no assisted injection needed now
    private val candleCreatorFn: CandleCreatorFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>() {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val CANDLE_TAG = "candles"
        private const val IMPULSE_TAG = "impulses"
    }

    // Factory might still be useful if TradeToCandle itself needs assisted inject
    interface Factory {
        fun create(windowDuration: Duration, defaultPrice: Double): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log(
            "Starting TradeToCandle transform with window duration: %s, Default Price: %.2f",
            windowDuration, defaultPrice
        )
        val pipeline = input.pipeline

        // 1. Key trades by currency pair
        val keyedTrades = input.apply("KeyByCurrencyPair",
            MapElements.into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Trade::class.java)))
                .via(SerializableFunction<Trade, KV<String, Trade>> { trade -> KV.of(trade.currencyPair, trade) })
        )

        // 2. Apply fixed windows
        val windowedTrades = keyedTrades.apply("WindowTrades",
            Window.into<KV<String, Trade>>(FixedWindows.of(windowDuration))
        )

        // 3. Aggregate trades into candles using the stateful DoFn
        val actualCandles: PCollection<KV<String, Candle>> = windowedTrades
            .apply("AggregateCandles", ParDo.of(candleCreatorFn))
            .setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))


        // 4. Create an impulse PCollection containing all known keys for each window
        val allKeys = currencyPairsSupplier.get().map { it.symbol() }
        if (allKeys.isEmpty()) {
            logger.atWarning().log("Currency pair supplier returned empty list. No default candles will be generated.")
            return actualCandles // Or handle as error?
        }

        val impulse = pipeline
            .apply("CreateAllKeys", Create.of(allKeys))
            .apply("MapKeysToKV", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.booleans()))
                .via(SerializableFunction<String, KV<String, Boolean>> { key -> KV.of(key, true) })
            )
            .apply("WindowImpulses", Window.into<KV<String, Boolean>>(FixedWindows.of(windowDuration))) // Match windowing

        // 5. CoGroupByKey actual candles and impulses
        val candleTag = TupleTag<Candle>(CANDLE_TAG)
        val impulseTag = TupleTag<Boolean>(IMPULSE_TAG)

        val joined = KeyedPCollectionTuple.of(candleTag, actualCandles)
            .and(impulseTag, impulse)
            .apply("JoinCandlesWithImpulses", CoGroupByKey.create())

        // 6. Process joined results: output actual candle or generate default
        val finalCandles = joined.apply("GenerateDefaults", ParDo.of(
            object : DoFn<KV<String, CoGbkResult>, KV<String, Candle>>() {
                @ProcessElement
                fun process(
                    @Element element: KV<String, CoGbkResult>,
                    context: ProcessContext,
                    window: BoundedWindow
                ) {
                    val currencyPair = element.key
                    val result = element.value
                    val candles = result.getAll(candleTag).toList()
                    val impulses = result.getAll(impulseTag).toList()

                    if (candles.isNotEmpty()) {
                        // Actual candle(s) found, output them
                        // Assuming CandleCreatorFn outputs at most one per key/window
                        candles.forEach { candle ->
                             // Output with the candle's original timestamp (first trade time)
                             context.outputWithTimestamp(
                                 KV.of(currencyPair, candle),
                                 Instant(Timestamps.toMillis(candle.timestamp))
                            )
                        }
                        logger.atFine().log("Output actual candle for %s", currencyPair)
                    } else if (impulses.isNotEmpty()) {
                        // No actual candle, but key was expected (impulse found) -> generate default
                        val windowEnd = window.maxTimestamp()
                        try {
                           val defaultCandle = createDefaultCandle(currencyPair, windowEnd, defaultPrice)
                            // Output default candle with window end timestamp
                            context.outputWithTimestamp(KV.of(currencyPair, defaultCandle), windowEnd)
                            logger.atFine().log("Output default candle for %s at window end %s", currencyPair, windowEnd)
                        } catch (e: Exception) {
                            logger.atSevere().withCause(e).log(
                                "Failed to generate or output default candle for %s at window end %s",
                                currencyPair, windowEnd
                            )
                        }
                    } else {
                        // Should not happen with CoGroupByKey unless input was empty?
                        logger.atWarning().log(
                            "Unexpected CoGbkResult for key %s: No candles and no impulses.",
                            currencyPair
                        )
                    }
                }
            }
        )).setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java))) // Set output type

        return finalCandles.setName("FinalCandlesWithDefaults")
    }

     // Helper function to create default candles - can be static or top-level
     companion object DefaultCandleCreator { // Keep logger accessible if needed
         private val logger = FluentLogger.forEnclosingClass() // Logger for default creation

         fun createDefaultCandle(currencyPair: String, windowEnd: Instant, defaultPrice: Double): Candle {
            logger.atFine().log("Creating default candle for %s at window end %s with price %.2f",
                 currencyPair, windowEnd, defaultPrice)

            // Basic validation, reuse logic from previous CandleCreatorFn fix attempt
             if (windowEnd.millis == Long.MIN_VALUE || windowEnd.millis == Long.MAX_VALUE ) {
                 logger.atSevere().log("Cannot create default candle for %s, windowEnd timestamp is invalid: %s", currencyPair, windowEnd)
                 throw IllegalStateException("Default candle generation failed due to invalid timestamp ($windowEnd) for pair $currencyPair")
             }
             val protoTimestamp = try {
                  Timestamps.fromMillis(windowEnd.millis)
             } catch (e: IllegalArgumentException) {
                  logger.atSevere().withCause(e).log("Failed to convert windowEnd Instant %s (millis: %d) to Protobuf Timestamp for %s",
                      windowEnd, windowEnd.millis, currencyPair)
                  throw IllegalStateException("Timestamp conversion failed for default candle $currencyPair", e)
             }

            return Candle.newBuilder()
                .setOpen(defaultPrice)
                .setHigh(defaultPrice)
                .setLow(defaultPrice)
                .setClose(defaultPrice)
                .setVolume(0.0)
                .setCurrencyPair(currencyPair)
                .setTimestamp(protoTimestamp)
                .build()
        }
     }
}
