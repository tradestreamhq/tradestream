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
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.Filter
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
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.util.ArrayList

/**
 * Alternative approach to testing FillForwardCandles using more focused tests.
 */
class FillForwardCandlesTest {

    @Rule
    @JvmField
    val pipeline: TestPipeline = TestPipeline.create()

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
        
        // Create a few original candles with non-zero volume
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

        // Verify all original candles are present in the output
        for (originalCandle in originalCandles) {
            val timestamp = Instant(Timestamps.toMillis(originalCandle.value.timestamp))
            
            // Filter to find the matching original candle in the output
            PAssert.that(
                result.apply("Filter${originalCandle.key}At${timestamp}", 
                    Filter.by { kv ->
                        kv.key == originalCandle.key && 
                        Timestamps.toMillis(kv.value.timestamp) == timestamp.millis &&
                        kv.value.volume > 0.0
                    })
            ).containsInAnyOrder(originalCandle)
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

        // Filter to get only fill-forward candles
        val fillForwardCandles = result.apply("GetFillForwardCandles", 
            Filter.by { kv ->
                Timestamps.toMillis(kv.value.timestamp) != baseTime.millis &&
                kv.key == "BTC/USD"
            })
        
        // Verify fill-forward candles properties
        PAssert.that(fillForwardCandles).satisfies { candles ->
            val candlesList = candles.toList()
            
            // Check we have fill-forward candles
            if (candlesList.isEmpty()) {
                return@satisfies "No fill-forward candles found"
            }
            
            // Check fill-forward candles have expected properties
            for (candle in candlesList) {
                // Check volume is zero
                if (candle.value.volume != 0.0) {
                    return@satisfies "Fill-forward candle has non-zero volume: ${candle.value.volume}"
                }
                
                // Check prices match the original close price
                if (candle.value.open != 50000.0 || 
                    candle.value.high != 50000.0 || 
                    candle.value.low != 50000.0 || 
                    candle.value.close != 50000.0) {
                    return@satisfies "Fill-forward candle prices don't match original close price: ${candle.value}"
                }
                
                // Check currency pair
                if (candle.value.currencyPair != "BTC/USD") {
                    return@satisfies "Fill-forward candle has unexpected currency pair: ${candle.value.currencyPair}"
                }
            }
            
            null // Return null to indicate success
        }
        
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
            // Advance watermark far beyond maxForwardIntervals
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(10)))
            .advanceWatermarkToInfinity()

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, maxForwardIntervals))

        // Count total number of candles for "BTC/USD"
        val btcCandleCount = result
            .apply("FilterBTC", Filter.by { kv -> kv.key == "BTC/USD" })
            .apply("Count", Count.globally())
        
        // Verify we have at most maxForwardIntervals + 1 candles (original + fill-forwards)
        PAssert.that(btcCandleCount).isEqualTo(maxForwardIntervals.toLong() + 1L)
        
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

        // Extract timestamps from all BTC/USD candles
        val timestamps = result
            .apply("FilterBTC", Filter.by { kv -> kv.key == "BTC/USD" })
            .apply("ExtractTimestamps", MapElements.via(
                object : SimpleFunction<KV<String, Candle>, Long>() {
                    override fun apply(input: KV<String, Candle>): Long {
                        return Timestamps.toMillis(input.value.timestamp)
                    }
                }
            ))
        
        // Check that we have candles at the expected timestamps
        PAssert.that(timestamps).satisfies { ts ->
            val timestampList = ts.toList().sorted()
            
            // Check we have the original timestamp
            if (!timestampList.contains(baseTime.millis)) {
                return@satisfies "Original timestamp not found"
            }
            
            // Check we have the expected fill-forward timestamps
            for (i in 1..maxForwardIntervals) {
                val expectedTimestamp = baseTime.plus(intervalDuration.multipliedBy(i)).millis
                if (!timestampList.contains(expectedTimestamp)) {
                    return@satisfies "Expected fill-forward timestamp not found: $expectedTimestamp"
                }
            }
            
            // Check we don't have too many timestamps
            if (timestampList.size > maxForwardIntervals + 1) {
                return@satisfies "Too many timestamps found. Expected ${maxForwardIntervals + 1}, got ${timestampList.size}"
            }
            
            null // Return null to indicate success
        }
        
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

        // Count candles per currency pair
        val candlesPerPair = result
            .apply("ExtractCurrencyPair", MapElements.via(
                object : SimpleFunction<KV<String, Candle>, String>() {
                    override fun apply(input: KV<String, Candle>): String {
                        return input.key
                    }
                }
            ))
            .apply("CountPerPair", Count.perElement())
        
        // Check that each pair has the expected number of candles
        PAssert.that(candlesPerPair).satisfies { counts ->
            val countsList = counts.toList()
            
            // Find the count for each pair
            val btcCount = countsList.find { it.key == "BTC/USD" }?.value ?: 0L
            val ethCount = countsList.find { it.key == "ETH/USD" }?.value ?: 0L
            
            // Each pair should have original + maxForwardIntervals candles
            val expectedCount = maxForwardIntervals.toLong() + 1L
            
            if (btcCount != expectedCount) {
                return@satisfies "Unexpected BTC/USD candle count. Expected $expectedCount, got $btcCount"
            }
            
            if (ethCount != expectedCount) {
                return@satisfies "Unexpected ETH/USD candle count. Expected $expectedCount, got $ethCount"
            }
            
            null // Return null to indicate success
        }
        
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
