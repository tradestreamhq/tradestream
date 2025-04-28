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
import org.apache.beam.sdk.transforms.Values
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test

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

    @Test
    fun testFillForwardOnEmptyWindow() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")

        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime)),
            baseTime
        )

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(candleWin1)
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(5)))
            .advanceWatermarkToInfinity()

        // Expected candles - original plus all fill-forward candles
        val expectedCandles = listOf(
            candleWin1.value.value,
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration)),  // at 1672567260
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(2))),  // at 1672567320
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(3))),  // at 1672567380
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(4))),  // at 1672567440
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(5))),  // at 1672567500
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(6)))   // at 1672567560
        )

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, 3))
            .apply(Values.create())

        PAssert.that(result).containsInAnyOrder(expectedCandles)

        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }

    @Test
    fun testMultipleFillForwardWindows() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")

        val candleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime)),
            baseTime
        )

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(candleWin1)
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(10)))
            .advanceWatermarkToInfinity()

        // Add all expected fill-forward candles
        val expectedFillForwardCandles = mutableListOf(candleWin1.value.value)
        // Add sequential candles from 1 to 7 minutes after base time
        for (i in 1L..7L) {
            expectedFillForwardCandles.add(createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(i))))
        }
        // Add the candle at 9 minutes after base time (1672567740)
        expectedFillForwardCandles.add(createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(9))))

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, 3))
            .apply(Values.create())

        PAssert.that(result).containsInAnyOrder(expectedFillForwardCandles)

        pipeline.run().waitUntilFinish(Duration.standardMinutes(2))
    }

    @Test
    fun testIndependentFillForwardForMultiplePairs() {
        val intervalDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00Z")

        val btcCandleWin1 = TimestampedValue.of(
            KV.of("BTC/USD", createCandle("BTC/USD", 50000.0, 1.0, baseTime)), baseTime
        )
        val ethCandleWin1 = TimestampedValue.of(
            KV.of("ETH/USD", createCandle("ETH/USD", 2000.0, 2.0, baseTime)), baseTime
        )

        val candleStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
            .addElements(btcCandleWin1, ethCandleWin1)
            .advanceWatermarkTo(baseTime.plus(intervalDuration.multipliedBy(10)))
            .advanceWatermarkToInfinity()

        val expectedCandles = mutableListOf(
            btcCandleWin1.value.value,
            ethCandleWin1.value.value,
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration)),
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(2))),
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(3))),
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(4))),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration)),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(2))),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(3))),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(4))),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(5))) // Add ETH candle at 1672567500
        )

        val result = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, 2))
            .apply(Values.create())

        PAssert.that(result).containsInAnyOrder(expectedCandles)

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
