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
import org.apache.beam.sdk.values.PCollection
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
            .advanceWatermarkTo(baseTime.plus(Duration.standardMinutes(5))) // advance sufficiently
            .advanceWatermarkToInfinity()

        val expectedFillForwardWin2 = createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration))

        val result: PCollection<Candle> = pipeline
            .apply(candleStream)
            .apply(fillForwardCandlesFactory.create(intervalDuration, 3))
            .apply(Values.create())

        PAssert.that(result).containsInAnyOrder(candleWin1.value, expectedFillForwardWin2)

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
            .advanceWatermarkTo(baseTime.plus(Duration.standardMinutes(10)))
            .advanceWatermarkToInfinity()

        val expectedFillForwardCandles = (1..3).map {
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(it)))
        } + candleWin1.value

        val result: PCollection<Candle> = pipeline
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
            .advanceWatermarkTo(baseTime.plus(Duration.standardMinutes(10)))
            .advanceWatermarkToInfinity()

        val expectedCandles = listOf(
            btcCandleWin1.value,
            ethCandleWin1.value,
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration)),
            createCandle("BTC/USD", 50000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(2))),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration)),
            createCandle("ETH/USD", 2000.0, 0.0, baseTime.plus(intervalDuration.multipliedBy(2)))
        )

        val result: PCollection<Candle> = pipeline
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
