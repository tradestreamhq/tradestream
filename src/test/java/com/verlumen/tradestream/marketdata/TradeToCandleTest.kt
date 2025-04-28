package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.SerializableFunction
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
import org.hamcrest.MatcherAssert.assertThat
import org.hamcrest.Matchers.closeTo 
import org.hamcrest.Matchers.containsInAnyOrder
import org.hamcrest.Matchers.equalTo


class TradeToCandleTest : Serializable {
    companion object {
        private const val serialVersionUID = 1L
        private const val TOLERANCE = 0.00001
    }

    @Rule
    @JvmField
    @Transient
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    // Bind the CandleCombineFn needed by the simplified TradeToCandle
    // Assuming CandleCombineFn has a default constructor or is otherwise injectable
    @Bind
    private val candleCombineFn = SlidingCandleAggregator.CandleCombineFn()

    private val btcUsd = CurrencyPair.fromSymbol("BTC/USD")
    private val ethUsd = CurrencyPair.fromSymbol("ETH/USD")

    @Before
    fun setUp() {
        // Configure Guice for testing
        val testModule = BoundFieldModule.of(this)
        val modules: List<Module> = listOf(
            testModule,
            // FactoryModuleBuilder for TradeToCandle
            FactoryModuleBuilder()
                .implement(TradeToCandle::class.java, TradeToCandle::class.java)
                .build(TradeToCandle.Factory::class.java)
        )
        val injector = Guice.createInjector(modules)
        injector.injectMembers(this)
    }

    /**
     * Verifies basic candle generation with trades present in the window.
     */
    @Test
    fun testBasicCandleGeneration() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val t1 = baseTime.plus(Duration.standardSeconds(15)) // 10:00:15
        val t2 = baseTime.plus(Duration.standardSeconds(45)) // 10:00:45

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, t1), t1
        )
        val tradeWin1Late = TimestampedValue.of(
            createTrade("BTC/USD", 50100.0, 0.5, t2), t2
        )

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1, tradeWin1Late)
            .advanceWatermarkTo(win1End.plus(Duration.millis(1))) // Advance watermark just past the end of the window
            .advanceWatermarkToInfinity()

        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
             // CombineFn uses the *first* trade's timestamp
            .setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).containsInAnyOrder(expectedBtcCandle)

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that no candle is output for a currency pair with no trades at all.
     * (This test remains valid as Combine.perKey won't output for keys with no data).
     */
    @Test
    fun testNoOutputForPairWithNoHistory() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration)
        val t1 = baseTime.plus(Duration.standardSeconds(30))

        // Only BTC trades, no ETH trades
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(1.0)
            .setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Only BTC candle should exist, no ETH candle
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Should produce exactly one candle", candles.size, equalTo(1))
                assertThat("Should only contain BTC/USD", candles[0].key, equalTo("BTC/USD"))
                // Compare actual candle content with expected
                val actualCandle = candles[0].value
                assertThat("Currency pair should match", actualCandle.currencyPair, equalTo(expectedBtcCandle.currencyPair))
                assertThat("Open price should match", actualCandle.open, closeTo(expectedBtcCandle.open, TOLERANCE))
                assertThat("High price should match", actualCandle.high, closeTo(expectedBtcCandle.high, TOLERANCE))
                assertThat("Low price should match", actualCandle.low, closeTo(expectedBtcCandle.low, TOLERANCE))
                assertThat("Close price should match", actualCandle.close, closeTo(expectedBtcCandle.close, TOLERANCE))
                assertThat("Volume should match", actualCandle.volume, closeTo(expectedBtcCandle.volume, TOLERANCE))
                 assertThat("Timestamp seconds should match", actualCandle.timestamp.seconds, equalTo(expectedBtcCandle.timestamp.seconds))
                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    // Helper to create trade objects
    private fun createTrade(
        currencyPair: String,
        price: Double,
        volume: Double,
        timestamp: Instant
    ): Trade {
        return Trade.newBuilder()
            .setCurrencyPair(currencyPair)
            .setPrice(price)
            .setVolume(volume)
            .setExchange("TEST")
            .setTradeId("test-${timestamp.millis}-${System.nanoTime()}")
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .build()
    }
}
