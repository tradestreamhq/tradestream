package com.verlumen.tradestream.marketdata

import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import java.io.Serializable
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Values
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/**
 * Test class for FillForwardCandles transform.
 */
class FillForwardCandlesTest : Serializable {
    companion object {
        // Use UPPER_SNAKE_CASE for constants [cite: 115]
        private const val SERIAL_VERSION_UID = 1L
        private const val MAX_FORWARD_INTERVALS = 10 // Reasonable value for testing
    }

    @Rule
    @JvmField
    @Transient
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Inject
    lateinit var fillForwardCandlesFactory: FillForwardCandles.Factory

    @Before
    fun setUp() {
        // Configure Guice for testing
        val modules: List<Module> = listOf(
            BoundFieldModule.of(this), // Binds fields annotated with @Bind
            // Factory for FillForwardCandlesFn
            FactoryModuleBuilder()
                .build(FillForwardCandlesFn.Factory::class.java),
            // Factory for FillForwardCandles PTransform
            FactoryModuleBuilder()
                .implement(FillForwardCandles::class.java, FillForwardCandles::class.java)
                .build(FillForwardCandles.Factory::class.java)
        )
        val injector = Guice.createInjector(modules)
        injector.injectMembers(this)
    }

    @Test
    fun testFillForwardOnEmptyWindow() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        // Timestamps represent the START of the interval for input/output candles
        // Use camelCase for variable names [cite: 123]
        val t1Start = baseTime // 10:00:00
        val t2Start = t1Start.plus(intervalDuration) // 10:01:00
        val t3Start = t2Start.plus(intervalDuration) // 10:02:00 (unused but kept for clarity)

        // Input: Only one actual candle for the first interval
        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1Start)),
            t1Start
        )

        // Wrap chained calls before the dot [cite: 58]
        val candleStream = TestStream.create(
            KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java))
        )
            .addElements(candleWin1)
            // Advance watermark past the end of the first interval + a bit to trigger timer setting
            .advanceWatermarkTo(t1Start.plus(intervalDuration).plus(Duration.millis(1)))
            // Advance watermark past the end of the second interval to trigger the timer for t2Start
            .advanceWatermarkTo(t2Start.plus(intervalDuration).plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1Start)
        // Fill-forward candle expected at the START of the empty interval (t2Start)
        // Wrap chained calls before the dot[cite: 58], indent lines [cite: 64]
        val expectedFillForwardWin2 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0) // Use close of candleWin1
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t2Start.millis)) // Timestamp is interval start
            .build()

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration, MAX_FORWARD_INTERVALS)
        // Wrap chained calls before the dot [cite: 58]
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        // Wrap arguments [cite: 56]
        PAssert.that(result)
            .containsInAnyOrder(expectedCandleWin1, expectedFillForwardWin2)

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testMultipleFillForwardWindows() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        // Use camelCase for variable names [cite: 123]
        val t1Start = baseTime // 10:00:00
        val t2Start = t1Start.plus(intervalDuration) // 10:01:00
        val t3Start = t2Start.plus(intervalDuration) // 10:02:00
        val t4Start = t3Start.plus(intervalDuration) // 10:03:00 (unused but kept for clarity)

        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1Start)),
            t1Start
        )

        // Wrap chained calls before the dot [cite: 58]
        val candleStream = TestStream.create(
            KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java))
        )
            .addElements(candleWin1)
            .advanceWatermarkTo(t1Start.plus(intervalDuration).plus(Duration.millis(1))) // Past win 1 end
            .advanceWatermarkTo(t2Start.plus(intervalDuration).plus(Duration.millis(1))) // Past win 2 end
            .advanceWatermarkTo(t3Start.plus(intervalDuration).plus(Duration.millis(1))) // Past win 3 end
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1Start)
        // Wrap chained calls before the dot[cite: 58], indent lines [cite: 64]
        val expectedFillForwardWin2 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t2Start.millis))
            .build()
        val expectedFillForwardWin3 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0) // Based on Win1 close (last actual)
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t3Start.millis))
            .build()

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration, MAX_FORWARD_INTERVALS)
        // Wrap chained calls before the dot [cite: 58]
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        // Wrap arguments [cite: 56]
        PAssert.that(result).containsInAnyOrder(
            expectedCandleWin1,
            expectedFillForwardWin2,
            expectedFillForwardWin3
        )

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testFillForwardResetsAfterNewTrade() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        // Use camelCase for variable names [cite: 123]
        val t1Start = baseTime // 10:00:00
        val t2Start = t1Start.plus(intervalDuration) // 10:01:00
        val t3Start = t2Start.plus(intervalDuration) // 10:02:00
        val t4Start = t3Start.plus(intervalDuration) // 10:03:00 (unused but kept for clarity)

        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1Start)),
            t1Start
        )
        // No candle for interval starting t2Start
        val candleWin3 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 51000.0, 0.5, t3Start)),
            t3Start
        )

        // Wrap chained calls before the dot [cite: 58]
        val candleStream = TestStream.create(
            KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java))
        )
            .addElements(candleWin1)
            // Advance watermark past Win1 end to trigger timer setting for t2Start
            .advanceWatermarkTo(t1Start.plus(intervalDuration).plus(Duration.millis(1)))
            // Advance watermark past Win2 end to trigger timer for t2Start
            .advanceWatermarkTo(t2Start.plus(intervalDuration).plus(Duration.millis(1)))
            .addElements(candleWin3) // Add Win3 candle
            // Advance watermark past Win3 end
            .advanceWatermarkTo(t3Start.plus(intervalDuration).plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1Start)
        // Wrap chained calls before the dot[cite: 58], indent lines [cite: 64]
        val expectedFillForwardWin2 = Candle.newBuilder() // Window 2 (fill-forward)
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t2Start.millis))
            .build()
        val expectedCandleWin3 = createCandle("BTC/USD", 51000.0, 0.5, t3Start)

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration, MAX_FORWARD_INTERVALS)
        // Wrap chained calls before the dot [cite: 58]
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        // Wrap arguments [cite: 56]
        PAssert.that(result).containsInAnyOrder(
            expectedCandleWin1,
            expectedFillForwardWin2,
            expectedCandleWin3
        )

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testIndependentFillForwardForMultiplePairs() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        // Use camelCase for variable names [cite: 123]
        val t1Start = baseTime // 10:00:00
        val t2Start = t1Start.plus(intervalDuration) // 10:01:00
        val t3Start = t2Start.plus(intervalDuration) // 10:02:00
        val t4Start = t3Start.plus(intervalDuration) // 10:03:00 (unused but kept for clarity)

        // Input Candles
        val btcWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1Start)),
            t1Start
        )
        val ethWin1 = TimestampedValue.of(
            KV.of("ETH/USD", createCandle("ETH/USD", 2000.0, 2.0, t1Start)),
            t1Start
        )
        val btcWin2 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50500.0, 0.5, t2Start)),
            t2Start
        )
        // No ETH candle for interval t2Start
        val ethWin3 = TimestampedValue.of(
            KV.of("ETH/USD", createCandle("ETH/USD", 2100.0, 1.5, t3Start)),
            t3Start
        )
        // No BTC candle for interval t3Start

        // Wrap chained calls before the dot [cite: 58]
        val candleStream = TestStream.create(
            KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java))
        )
            .addElements(btcWin1, ethWin1) // Both in window 1
            .advanceWatermarkTo(t1Start.plus(intervalDuration).plus(Duration.millis(1))) // Trigger t2
            .addElements(btcWin2) // Only BTC in window 2
            .advanceWatermarkTo(t2Start.plus(intervalDuration).plus(Duration.millis(1))) // Trigger t3
            .addElements(ethWin3) // Only ETH in window 3
            .advanceWatermarkTo(t3Start.plus(intervalDuration).plus(Duration.millis(1))) // Trigger t4
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expBtcWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1Start)
        val expBtcWin2 = createCandle("BTC/USD", 50500.0, 0.5, t2Start)
        // Wrap chained calls before the dot[cite: 58], indent lines [cite: 64]
        val expBtcWin3FF = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50500.0) // Use close of btcWin2
            .setHigh(50500.0)
            .setLow(50500.0)
            .setClose(50500.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t3Start.millis))
            .build()
        val expEthWin1 = createCandle("ETH/USD", 2000.0, 2.0, t1Start)
        val expEthWin2FF = Candle.newBuilder()
            .setCurrencyPair("ETH/USD")
            .setOpen(2000.0) // Use close of ethWin1
            .setHigh(2000.0)
            .setLow(2000.0)
            .setClose(2000.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t2Start.millis))
            .build()
        val expEthWin3 = createCandle("ETH/USD", 2100.0, 1.5, t3Start)

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration, MAX_FORWARD_INTERVALS)
        // Wrap chained calls before the dot [cite: 58]
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        // Wrap arguments [cite: 56]
        PAssert.that(result)
            .containsInAnyOrder(
                expBtcWin1, expBtcWin2, expBtcWin3FF,
                expEthWin1, expEthWin2FF, expEthWin3
            )

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testMaxForwardIntervalLimit() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val smallMaxIntervals = 3 // Smaller limit for this test
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1Start = baseTime // 10:00:00 (unused but kept for clarity)

        // Generate timestamps for many intervals
        // Add space around binary operator `..` is incorrect per style guide [cite: 84]
        // Use lambda argument name other than 'i' if possible, but 'i' is common for index.
        val timestamps = (0..15).map { index ->
            baseTime.plus(intervalDuration.multipliedBy(index.toLong()))
        }

        // Just one actual candle at the beginning
        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, timestamps[0])),
            timestamps[0]
        )

        // Create stream with a single input candle, then advance watermark past many intervals
        // Wrap chained calls before the dot [cite: 58]
        val candleStream = TestStream.create(
            KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java))
        )
            .addElements(candleWin1)

        // Add watermark advancements for each interval, but limit to smallMaxIntervals + 1
        // to prevent excessive timer creation
        // Add spaces around lambda arrow `->` [cite: 79]
        val streamWithWatermarks = timestamps.drop(1).take(smallMaxIntervals + 1).fold(candleStream) { stream, timestamp ->
            stream.advanceWatermarkTo(timestamp.plus(Duration.millis(1)))
        }

        val finalStream = streamWithWatermarks.advanceWatermarkToInfinity()

        // Expected Candles: original + smallMaxIntervals fill-forward candles
        val expectedCandles = mutableListOf<Candle>()
        // Add the original candle
        expectedCandles.add(createCandle("BTC/USD", 50000.0, 1.0, timestamps[0]))

        // Add the expected fill-forward candles (only up to smallMaxIntervals)
        // Add space around binary operator `..` is incorrect per style guide [cite: 84]
        for (i in 1..smallMaxIntervals) {
            // Wrap chained calls before the dot[cite: 58], indent lines [cite: 64]
            expectedCandles.add(
                Candle.newBuilder()
                    .setCurrencyPair("BTC/USD")
                    .setOpen(50000.0)
                    .setHigh(50000.0)
                    .setLow(50000.0)
                    .setClose(50000.0)
                    .setVolume(0.0)
                    .setTimestamp(Timestamps.fromMillis(timestamps[i].millis))
                    .build()
            )
        }

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration, smallMaxIntervals)
        // Wrap chained calls before the dot
        val result: PCollection<Candle> = pipeline
            .apply(finalStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert - should only contain original + smallMaxIntervals fill-forward candles
        // Wrap arguments
        PAssert.that(result).containsInAnyOrder(expectedCandles)

        // Add timeout to prevent test from hanging
        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }

    // Helper to create candle objects (simplified for testing)
    // Wrap parameters onto own lines, +4 indent
    private fun createCandle(
        currencyPair: String,
        price: Double,
        volume: Double,
        timestamp: Instant
    ): Candle {
        // In this test setup, the input candle's timestamp represents the *start* of its interval
        // Wrap chained calls before the dot[cite: 58], indent lines [cite: 64]
        return Candle.newBuilder()
            .setCurrencyPair(currencyPair)
            .setOpen(price) // Simplification: O=H=L=C=price
            .setHigh(price)
            .setLow(price)
            .setClose(price)
            .setVolume(volume)
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .build()
    }
}
