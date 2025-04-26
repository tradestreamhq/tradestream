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
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.*
import org.joda.time.Duration
import org.joda.time.Instant
import java.util.function.Supplier
import com.google.protobuf.util.Timestamps

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
    private val candleCreatorFn: CandleCreatorFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>() {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val CANDLE_TAG = "candles"
        private const val IMPULSE_TAG = "impulses"
        
        // Min/max valid timestamps for Protobuf (in seconds)
        private const val MIN_VALID_TIMESTAMP_SECONDS = -62135596800L  // 0001-01-01T00:00:00Z
        private const val MAX_VALID_TIMESTAMP_SECONDS = 253402300799L  // 9999-12-31T23:59:59Z
        
        fun createDefaultCandle(currencyPair: String, windowEnd: Instant, defaultPrice: Double): Candle {
            logger.atFine().log("Creating default candle for %s at window end %s with price %.2f",
                currencyPair, windowEnd, defaultPrice)

            // Handle extreme timestamp values
            if (windowEnd.millis == Long.MIN_VALUE || windowEnd.millis == Long.MAX_VALUE) {
                logger.atWarning().log("Invalid window end timestamp: %s. Using current time instead.", windowEnd)
                // Use current time as fallback
                val currentTimeMillis = System.currentTimeMillis()
                val protoTimestamp = Timestamps.fromMillis(currentTimeMillis)
                
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
            
            try {
                // Check if timestamp is within valid Protobuf range
                val timestampSeconds = windowEnd.getMillis() / 1000
                if (timestampSeconds < MIN_VALID_TIMESTAMP_SECONDS || timestampSeconds > MAX_VALID_TIMESTAMP_SECONDS) {
                    logger.atWarning().log(
                        "Window end timestamp %s (seconds: %d) is outside valid Protobuf range. Using current time instead.",
                        windowEnd, timestampSeconds
                    )
                    // Use current time as fallback
                    val currentTimeMillis = System.currentTimeMillis()
                    val protoTimestamp = Timestamps.fromMillis(currentTimeMillis)
                    
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
                
                val protoTimestamp = Timestamps.fromMillis(windowEnd.millis)
                return Candle.newBuilder()
                    .setOpen(defaultPrice)
                    .setHigh(defaultPrice)
                    .setLow(defaultPrice)
                    .setClose(defaultPrice)
                    .setVolume(0.0)
                    .setCurrencyPair(currencyPair)
                    .setTimestamp(protoTimestamp)
                    .build()
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log(
                    "Failed to convert timestamp for %s. Using current time instead.", currencyPair
                )
                // Use current time as fallback in case of any error
                val currentTimeMillis = System.currentTimeMillis()
                val protoTimestamp = Timestamps.fromMillis(currentTimeMillis)
                
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
            .apply("AggregateCandles", ParDo.of(candleCreatorFn))
            .setTypeDescriptor(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Candle::class.java)))

        val allKeys = currencyPairsSupplier.get().map { it.symbol() }
        if (allKeys.isEmpty()) {
            logger.atWarning().log("Currency pair supplier returned empty list. No default candles will be generated.")
            return actualCandles
        }

        val impulse = pipeline
            .apply("CreateAllKeys", Create.of(allKeys))
            .apply("MapKeysToKV", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.booleans()))
                .via(SerializableFunction<String, KV<String, Boolean>> { key -> KV.of(key, true) })
            )
            .apply("WindowImpulses", Window.into<KV<String, Boolean>>(FixedWindows.of(windowDuration)))

        val candleTag = TupleTag<Candle>(CANDLE_TAG)
        val impulseTag = TupleTag<Boolean>(IMPULSE_TAG)

        val joined = KeyedPCollectionTuple.of(candleTag, actualCandles)
            .and(impulseTag, impulse)
            .apply("JoinCandlesWithImpulses", CoGroupByKey.create())

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
                        candles.forEach { candle ->
                            // Always use the current window's timestamp instead of the candle's timestamp
                            // to avoid timestamp skew issues
                            context.output(KV.of(currencyPair, candle))
                        }
                        logger.atFine().log("Output actual candle for %s", currencyPair)
                    } else if (impulses.isNotEmpty()) {
                        val windowEnd = window.maxTimestamp()
                        try {
                            val defaultCandle = createDefaultCandle(currencyPair, windowEnd, defaultPrice)
                            // Use output instead of outputWithTimestamp to use the current element's timestamp
                            context.output(KV.of(currencyPair, defaultCandle))
                            logger.atFine().log("Output default candle for %s at window end %s", currencyPair, windowEnd)
                        } catch (e: Exception) {
                            logger.atSevere().withCause(e).log(
                                "Failed to generate or output default candle for %s at window end %s",
                                currencyPair, windowEnd
                            )
                        }
                    } else {
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
