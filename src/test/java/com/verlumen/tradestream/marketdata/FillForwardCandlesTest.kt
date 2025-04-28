package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Count
// Import SerializableFunction
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.transforms.Filter // Keep Filter import
import org.apache.beam.sdk.transforms.GroupByKey
import org.apache.beam.sdk.transforms.Keys
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SimpleFunction
import org.apache.beam.sdk.transforms.Values
import org.apache.beam.sdk.transforms.WithTimestamps
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TimestampedValue
import org.apache.beam.sdk.values.TypeDescriptor
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.util.ArrayList
import java.io.Serializable

/**
 * Alternative approach to testing FillForwardCandles using more focused tests.
 */
class FillForwardCandlesTest {

    @Rule
    @JvmField
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Inject
    lateinit var fillForwardCandlesFactory: FillForwardCandles.Factory

    @Before
    fun setUp() {
        val modules: List<Module> = listOf(
            BoundFieldModule.of(this),
            FactoryModuleBuilder().build(FillForwardCandlesFn.Factory::class.java),
            FactoryModuleBuilder()
                .implement(FillForwardCandles::class.java, FillForwardCandles::class.java)
                .build(FillForwardCandles.Factory::class.java)
        )
        Guice.createInjector(modules).injectMembers(this)
    }

    /**
     * Test that the transform preserves original candles.
     */
    @Test
    fun testPreservesOriginalCandles() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")

        val originalCandles = listOf(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime)),
            KV.of("ETH/USD", createCandle("ETH/USD", 2000.0, 2.0, baseTime)),
            KV.of("BTC/USD", createCandle("BTC/USD", 51000.0, 1.5, baseTime.plus(intervalDuration.multipliedBy(5))))
        )

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(
                TimestampedValue.of(originalCandles[0], baseTime),
                TimestampedValue.of(originalCandles[1], baseTime),
                TimestampedValue.of(originalCandles[2], baseTime.plus(intervalDuration.multipliedBy(5)))
            )
            .advanceWatermarkToInfinity()

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, 3))

        for (originalCandle in originalCandles) {
            val timestamp = Instant(Timestamps.toMillis(originalCandle.value.timestamp))

            PAssert.that(
                result.apply("Filter${originalCandle.key}At${timestamp}",
                    // *** FIX: Remove explicit type args for Filter.by ***
                    Filter.by(SerializableFunction { kv: KV<String, Candle> ->
                        kv.key == originalCandle.key &&
                        Timestamps.toMillis(kv.value.timestamp) == timestamp.millis &&
                        kv.value.volume > 0.0
                    })
                )
            ).containsInAnyOrder(listOf(originalCandle))
        }

        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }

    /**
     * Test that fill-forward candles have expected properties.
     */
    @Test
    fun testFillForwardCandleProperties() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")
        val maxForwardIntervals = 3

        val originalCandle = KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime))

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(TimestampedValue.of(originalCandle, baseTime))
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(5)))
            .advanceWatermarkToInfinity()

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, maxForwardIntervals))

        val fillForwardCandles: PCollection<KV<String, Candle>> = result.apply("GetFillForwardCandles",
            // *** FIX: Remove explicit type args for Filter.by ***
            Filter.by(SerializableFunction { kv: KV<String, Candle> ->
                Timestamps.toMillis(kv.value.timestamp) != baseTime.millis &&
                kv.key == "BTC/USD"
            })
        )

        // Verify fill-forward candles properties
        // *** FIX: Change return type to Void? and throw AssertionError on failure ***
        PAssert.that(fillForwardCandles).satisfies(SerializableFunction<Iterable<KV<String, Candle>>, Void?> { candles ->
            val candlesList = candles.toList()
            var errorMessage: String? = null // Use var to modify

            if (candlesList.isEmpty()) {
                errorMessage = "No fill-forward candles found" // Assign error message
            } else {
                for (candle in candlesList) {
                    if (candle.value.volume != 0.0) {
                        errorMessage = "Fill-forward candle has non-zero volume: ${candle.value.volume}"
                        break // Exit loop on first failure
                    }
                    if (candle.value.open != 50000.0 ||
                        candle.value.high != 50000.0 ||
                        candle.value.low != 50000.0 ||
                        candle.value.close != 50000.0) {
                        errorMessage = "Fill-forward candle prices don't match original close price: ${candle.value}"
                        break
                    }
                    if (candle.value.currencyPair != "BTC/USD") {
                        errorMessage = "Fill-forward candle has unexpected currency pair: ${candle.value.currencyPair}"
                        break
                    }
                }
            }

            // Throw AssertionError on failure, return null on success
            if (errorMessage != null) {
               throw AssertionError(errorMessage)
            }
            null // Return null for Void?
        })


        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }


    /**
     * Test that the maxForwardIntervals parameter is respected.
     */
    @Test
    fun testMaxForwardIntervalsRespected() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")
        val maxForwardIntervals = 3 // Set a small limit

        val originalCandle = KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime))

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(TimestampedValue.of(originalCandle, baseTime))
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(10)))
            .advanceWatermarkToInfinity()

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, maxForwardIntervals))

        val btcCandleCount: PCollection<Long> = result
             // *** FIX: Remove explicit type args for Filter.by ***
             .apply("FilterBTC", Filter.by(SerializableFunction { kv: KV<String, Candle> -> kv.key == "BTC/USD" }))
             .apply("Count", Count.globally<KV<String, Candle>>())

        PAssert.thatSingleton(btcCandleCount).isEqualTo(maxForwardIntervals.toLong() + 1L)

        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }


    /**
     * Test that fill-forward candles are created at expected timestamps.
     */
    @Test
    fun testFillForwardTimestamps() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")
        val maxForwardIntervals = 3

        val originalCandle = KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime))

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(TimestampedValue.of(originalCandle, baseTime))
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(5)))
            .advanceWatermarkToInfinity()

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, maxForwardIntervals))

        val timestamps: PCollection<Long> = result
            // *** FIX: Remove explicit type args for Filter.by ***
            .apply("FilterBTC", Filter.by(SerializableFunction { kv: KV<String, Candle> -> kv.key == "BTC/USD" }))
             .apply("ExtractTimestamps", MapElements.into(TypeDescriptor.of(Long::class.java)).via(
                 SerializableFunction { kv: KV<String, Candle> ->
                     Timestamps.toMillis(kv.value.timestamp)
                 }
             ))

        // Check that we have candles at the expected timestamps
        // *** FIX: Change return type to Void? and throw AssertionError on failure ***
        PAssert.that(timestamps).satisfies(SerializableFunction<Iterable<Long>, Void?> { ts ->
            val timestampList = ts.toList().sorted()
            var errorMessage: String? = null

            if (!timestampList.contains(baseTime.millis)) {
                errorMessage = "Original timestamp not found"
            } else {
                // Check we have the expected fill-forward timestamps
                for (i in 1..maxForwardIntervals) {
                    val expectedTimestamp = baseTime.plus(intervalDuration.multipliedBy(i.toLong())).millis
                    if (!timestampList.contains(expectedTimestamp)) {
                        errorMessage = "Expected fill-forward timestamp not found: $expectedTimestamp"
                        break
                    }
                }
                // Check we don't have too many timestamps (only if no previous error)
                if (errorMessage == null && timestampList.size > maxForwardIntervals + 1) {
                   errorMessage = "Too many timestamps found. Expected ${maxForwardIntervals + 1}, got ${timestampList.size}"
                }
            }

            // Throw AssertionError on failure, return null on success
            if (errorMessage != null) {
               throw AssertionError(errorMessage)
            }
            null // Return null for Void?
        })


        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }

    /**
     * Test that different currency pairs are handled independently.
     */
    @Test
    fun testIndependentCurrencyPairs() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")
        val maxForwardIntervals = 3

        val btcCandle = KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime))
        val ethCandle = KV.of("ETH/USD", createCandle("ETH/USD", 2000.0, 2.0, baseTime))

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(
                TimestampedValue.of(btcCandle, baseTime),
                TimestampedValue.of(ethCandle, baseTime)
            )
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(5)))
            .advanceWatermarkToInfinity()

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, maxForwardIntervals))

        val candlesPerPair: PCollection<KV<String, Long>> = result
             .apply("ExtractCurrencyPair", MapElements.into(TypeDescriptor.of(String::class.java)).via(
                 SerializableFunction { kv: KV<String, Candle> -> kv.key }
             ))
            .apply("CountPerPair", Count.perElement())

        // Check that each pair has the expected number of candles
        // *** FIX: Change return type to Void? and throw AssertionError on failure ***
        PAssert.that(candlesPerPair).satisfies(SerializableFunction<Iterable<KV<String, Long>>, Void?> { counts ->
            val countsList = counts.toList()
            val btcCount = countsList.find { it.key == "BTC/USD" }?.value ?: 0L
            val ethCount = countsList.find { it.key == "ETH/USD" }?.value ?: 0L
            val expectedCount = maxForwardIntervals.toLong() + 1L
            var errorMessage: String? = null

            if (btcCount != expectedCount) {
                errorMessage = "Unexpected BTC/USD candle count. Expected $expectedCount, got $btcCount"
            } else if (ethCount != expectedCount) {
                errorMessage = "Unexpected ETH/USD candle count. Expected $expectedCount, got $ethCount"
            }

            // Throw AssertionError on failure, return null on success
            if (errorMessage != null) {
                throw AssertionError(errorMessage)
            }
            null // Return null for Void?
        })


        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }


    private fun createCandle(pair: String, price: Double, volume: Double, timestamp: Instant): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(pair)
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .setOpen(price)
            .setHigh(price)
            .setLow(price)
            .setClose(price)
            .setVolume(volume)
            .build()
    }
}
