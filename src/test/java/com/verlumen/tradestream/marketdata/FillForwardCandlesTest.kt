package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.BoundFieldModule
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
import java.io.Serializable
import com.google.protobuf.util.Timestamps
import com.google.inject.AbstractModule

/**
 * Test class for FillForwardCandles transform.
 */
class FillForwardCandlesTest : Serializable {
    companion object {
        private const val serialVersionUID = 1L
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
        val t1_start = baseTime // 10:00:00
        val t2_start = t1_start.plus(intervalDuration) // 10:01:00
        val t3_start = t2_start.plus(intervalDuration) // 10:02:00

        // Input: Only one actual candle for the first interval
        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1_start)), t1_start
        )

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(candleWin1)
            // Advance watermark past the end of the first interval + a bit to trigger timer setting
            .advanceWatermarkTo(t1_start.plus(intervalDuration).plus(Duration.millis(1)))
             // Advance watermark past the end of the second interval to trigger the timer for t2_start
            .advanceWatermarkTo(t2_start.plus(intervalDuration).plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1_start)
        // Fill-forward candle expected at the START of the empty interval (t2_start)
        val expectedFillForwardWin2 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0) // Use close of candleWin1
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(t2_start.millis)) // Timestamp is interval start
            .build()

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration)
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).containsInAnyOrder(expectedCandleWin1, expectedFillForwardWin2)

        pipeline.run().waitUntilFinish()
    }

     @Test
    fun testMultipleFillForwardWindows() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1_start = baseTime // 10:00:00
        val t2_start = t1_start.plus(intervalDuration) // 10:01:00
        val t3_start = t2_start.plus(intervalDuration) // 10:02:00
        val t4_start = t3_start.plus(intervalDuration) // 10:03:00

        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1_start)), t1_start
        )

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(candleWin1)
            .advanceWatermarkTo(t1_start.plus(intervalDuration).plus(Duration.millis(1))) // Past win 1 end
            .advanceWatermarkTo(t2_start.plus(intervalDuration).plus(Duration.millis(1))) // Past win 2 end
            .advanceWatermarkTo(t3_start.plus(intervalDuration).plus(Duration.millis(1))) // Past win 3 end
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1_start)
        val expectedFillForwardWin2 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(t2_start.millis))
            .build()
        val expectedFillForwardWin3 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0) // Based on Win1 close (last actual)
            .setClose(50000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(t3_start.millis))
            .build()

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration)
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).containsInAnyOrder(
            expectedCandleWin1, expectedFillForwardWin2, expectedFillForwardWin3
        )

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testFillForwardResetsAfterNewTrade() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1_start = baseTime // 10:00:00
        val t2_start = t1_start.plus(intervalDuration) // 10:01:00
        val t3_start = t2_start.plus(intervalDuration) // 10:02:00
        val t4_start = t3_start.plus(intervalDuration) // 10:03:00


        val candleWin1 = TimestampedValue.of(KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1_start)), t1_start)
        // No candle for interval starting t2_start
        val candleWin3 = TimestampedValue.of(KV.of("BTC/USD", createCandle("BTC/USD", 51000.0, 0.5, t3_start)), t3_start)

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(candleWin1)
            // Advance watermark past Win1 end to trigger timer setting for t2_start
            .advanceWatermarkTo(t1_start.plus(intervalDuration).plus(Duration.millis(1)))
             // Advance watermark past Win2 end to trigger timer for t2_start
            .advanceWatermarkTo(t2_start.plus(intervalDuration).plus(Duration.millis(1)))
            .addElements(candleWin3) // Add Win3 candle
            // Advance watermark past Win3 end
             .advanceWatermarkTo(t3_start.plus(intervalDuration).plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1_start)
        val expectedFillForwardWin2 = Candle.newBuilder() // Window 2 (fill-forward)
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(t2_start.millis))
            .build()
        val expectedCandleWin3 = createCandle("BTC/USD", 51000.0, 0.5, t3_start)


        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration)
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).containsInAnyOrder(
            expectedCandleWin1, expectedFillForwardWin2, expectedCandleWin3
        )

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testIndependentFillForwardForMultiplePairs() {
        // Arrange
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1_start = baseTime // 10:00:00
        val t2_start = t1_start.plus(intervalDuration) // 10:01:00
        val t3_start = t2_start.plus(intervalDuration) // 10:02:00
        val t4_start = t3_start.plus(intervalDuration) // 10:03:00

        // Input Candles
        val btcWin1 = TimestampedValue.of(KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, t1_start)), t1_start)
        val ethWin1 = TimestampedValue.of(KV.of("ETH/USD", createCandle("ETH/USD", 2000.0, 2.0, t1_start)), t1_start)
        val btcWin2 = TimestampedValue.of(KV.of("BTC/USD", createCandle("BTC/USD", 50500.0, 0.5, t2_start)), t2_start)
        // No ETH candle for interval t2_start
        val ethWin3 = TimestampedValue.of(KV.of("ETH/USD", createCandle("ETH/USD", 2100.0, 1.5, t3_start)), t3_start)
        // No BTC candle for interval t3_start

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(btcWin1, ethWin1) // Both in window 1
            .advanceWatermarkTo(t1_start.plus(intervalDuration).plus(Duration.millis(1))) // Trigger timers for t2_start
            .addElements(btcWin2) // Only BTC in window 2
            .advanceWatermarkTo(t2_start.plus(intervalDuration).plus(Duration.millis(1))) // Trigger timers for t3_start
            .addElements(ethWin3) // Only ETH in window 3
            .advanceWatermarkTo(t3_start.plus(intervalDuration).plus(Duration.millis(1))) // Trigger timers for t4_start
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expBtcWin1 = createCandle("BTC/USD", 50000.0, 1.0, t1_start)
        val expBtcWin2 = createCandle("BTC/USD", 50500.0, 0.5, t2_start)
        val expBtcWin3FF = Candle.newBuilder().setCurrencyPair("BTC/USD").setOpen(50500.0).setHigh(50500.0).setLow(50500.0).setClose(50500.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(t3_start.millis)).build()
        val expEthWin1 = createCandle("ETH/USD", 2000.0, 2.0, t1_start)
        val expEthWin2FF = Candle.newBuilder().setCurrencyPair("ETH/USD").setOpen(2000.0).setHigh(2000.0).setLow(2000.0).setClose(2000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(t2_start.millis)).build()
        val expEthWin3 = createCandle("ETH/USD", 2100.0, 1.5, t3_start)

        // Act
        val transform = fillForwardCandlesFactory.create(intervalDuration)
        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply("FillForward", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result)
            .containsInAnyOrder(
                expBtcWin1, expBtcWin2, expBtcWin3FF,
                expEthWin1, expEthWin2FF, expEthWin3
            )

        pipeline.run().waitUntilFinish()
    }


    // Helper to create candle objects (simplified for testing)
    private fun createCandle(
        currencyPair: String,
        price: Double,
        volume: Double,
        timestamp: Instant
    ): Candle {
        // In this test setup, the input candle's timestamp represents the *start* of its interval
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
