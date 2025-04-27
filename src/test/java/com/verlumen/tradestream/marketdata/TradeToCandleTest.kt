package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
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
import org.hamcrest.MatcherAssert.assertThat // Direct import for assertThat
import org.hamcrest.Matchers.closeTo        // Direct import for closeTo
import org.hamcrest.Matchers.containsInAnyOrder // Direct import for containsInAnyOrder
import org.hamcrest.Matchers.equalTo         // Direct import for equalTo

/**
 * Test class for TradeToCandle that verifies both actual candle generation
 * and fill-forward behavior when no trades occur.
 */
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

    // Inject CandleCreatorFn directly if needed for setup, otherwise rely on TradeToCandleFactory
    @Inject
    lateinit var candleCreatorFn: CandleCreatorFn

    private val btcUsd = CurrencyPair.fromSymbol("BTC/USD")
    private val ethUsd = CurrencyPair.fromSymbol("ETH/USD")

    @Before
    fun setUp() {
        // Configure Guice for testing
        val testModule = BoundFieldModule.of(this)
        val modules: List<Module> = listOf(
            testModule,
            object : AbstractModule() {
                override fun configure() {
                    // Bind CandleCreatorFn if it's needed directly or rely on its injection into TradeToCandle
                    bind(CandleCreatorFn::class.java)
                }
            },
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
        // val win1End = baseTime.plus(windowDuration) // 10:01:00 // Not needed for watermark advance in this test
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
            .advanceWatermarkToInfinity()

        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(t1.millis)) // Timestamp of first trade in window
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).containsInAnyOrder(expectedBtcCandle) // Check contents directly

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that no candle is output for a currency pair with no history.
     */
    @Test
    fun testNoOutputForPairWithNoHistory() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(30))

        // Only BTC trades, no ETH trades
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
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

    /**
     * Verifies fill-forward behavior when a window has no trades.
     */
    @Test
    fun testFillForwardOnEmptyWindow() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val win2End = win1End.plus(windowDuration)  // 10:02:00
        val t1 = baseTime.plus(Duration.standardSeconds(30)) // Trade time

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, t1), t1
        )

        // TestStream with trade in window 1, no trades in window 2
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Trade in window 1
             // Correctly advance watermark past the window end to trigger finalization
            .advanceWatermarkTo(win1End.plus(Duration.standardSeconds(1)))
            // Advance watermark past the second window end to trigger its finalization (empty)
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkToInfinity()

        // Expected candle for window 1 (actual trades)
        val expectedCandleWin1 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(1.0)
            .setTimestamp(Timestamps.fromMillis(t1.millis)) // Window 1 candle timestamp is based on first trade
            .build()

        // Expected fill-forward candle for window 2
        val expectedFillForwardWin2 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0) // Same as close from window 1
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0) // Zero volume indicates fill-forward
            .setTimestamp(Timestamps.fromMillis(win2End.millis)) // Window 2 *end time* for fill-forward
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert - Should contain both the original candle and the fill-forward candle
        PAssert.that(result).containsInAnyOrder(expectedCandleWin1, expectedFillForwardWin2)

        pipeline.run().waitUntilFinish()
    }


    /**
     * Verifies that fill-forward continues across multiple empty windows.
     */
    @Test
    fun testMultipleFillForwardWindows() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration)     // 10:01:00
        val win2End = win1End.plus(windowDuration)      // 10:02:00
        val win3End = win2End.plus(windowDuration)      // 10:03:00
        val t1 = baseTime.plus(Duration.standardSeconds(30)) // Trade time

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, t1), t1
        )

        // TestStream with trade in window 1, no trades in windows 2 and 3
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Trade in window 1
            .advanceWatermarkTo(win1End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkTo(win3End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(1.0).setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()
        val expectedFillForwardWin2 = Candle.newBuilder() // Window 2 fill-forward
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(win2End.millis))
            .build()
        val expectedFillForwardWin3 = Candle.newBuilder() // Window 3 fill-forward
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(win3End.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert - Should have 3 candles (1 actual, 2 fill-forward)
        PAssert.that(result).containsInAnyOrder(
            expectedCandleWin1, expectedFillForwardWin2, expectedFillForwardWin3
        )

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that fill-forward stops when trades resume.
     */
    @Test
    fun testFillForwardResetsAfterNewTrade() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration)     // 10:01:00
        val win2End = win1End.plus(windowDuration)      // 10:02:00
        val win3End = win2End.plus(windowDuration)      // 10:03:00

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30
        val t3 = win2End.plus(Duration.standardSeconds(30))  // 10:02:30

        val tradeWin1 = TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
        val tradeWin3 = TimestampedValue.of(createTrade("BTC/USD", 51000.0, 0.5, t3), t3)

        // TestStream with trades in windows 1 and 3, no trades in window 2
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1)
            // Advance watermark past Win1 and Win2 to trigger their finalizations
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1)))
            .addElements(tradeWin3) // Add Win3 trade
            // Advance watermark past Win3 end
             .advanceWatermarkTo(win3End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandleWin1 = Candle.newBuilder() // Window 1 (actual)
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(1.0).setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()
        val expectedFillForwardWin2 = Candle.newBuilder() // Window 2 (fill-forward)
            .setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0)
            .setClose(50000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(win2End.millis))
            .build()
        val expectedCandleWin3 = Candle.newBuilder() // Window 3 (actual)
            .setCurrencyPair("BTC/USD").setOpen(51000.0).setHigh(51000.0).setLow(51000.0)
            .setClose(51000.0).setVolume(0.5).setTimestamp(Timestamps.fromMillis(t3.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).containsInAnyOrder(
            expectedCandleWin1, expectedFillForwardWin2, expectedCandleWin3
        )

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that fill-forward works independently for different currency pairs.
     */
    @Test
    fun testIndependentFillForwardForMultiplePairs() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration)     // 10:01:00
        val win2End = win1End.plus(windowDuration)      // 10:02:00
        val win3End = win2End.plus(windowDuration)      // 10:03:00

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30
        val t2 = win1End.plus(Duration.standardSeconds(30))  // 10:01:30
        val t3 = win2End.plus(Duration.standardSeconds(30))  // 10:02:30

        // Create trades with timestamps
        val btcWin1 = TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
        val ethWin1 = TimestampedValue.of(createTrade("ETH/USD", 2000.0, 2.0, t1), t1)
        val btcWin2 = TimestampedValue.of(createTrade("BTC/USD", 50500.0, 0.5, t2), t2)
        // No ETH trade in Win2
        val ethWin3 = TimestampedValue.of(createTrade("ETH/USD", 2100.0, 1.5, t3), t3)
        // No BTC trade in Win3

        // TestStream with different trade patterns for BTC and ETH
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(btcWin1, ethWin1) // Both in window 1
            .advanceWatermarkTo(win1End.plus(Duration.standardSeconds(1)))
            .addElements(btcWin2) // Only BTC in window 2
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1)))
            .addElements(ethWin3) // Only ETH in window 3
            .advanceWatermarkTo(win3End.plus(Duration.standardSeconds(1))) // Ensure win3 finalizes
            .advanceWatermarkToInfinity()

        // Expected Candles
        // BTC: win1(actual), win2(actual), win3(fill-forward)
        val expBtcWin1 = Candle.newBuilder().setCurrencyPair("BTC/USD").setOpen(50000.0).setHigh(50000.0).setLow(50000.0).setClose(50000.0).setVolume(1.0).setTimestamp(Timestamps.fromMillis(t1.millis)).build()
        val expBtcWin2 = Candle.newBuilder().setCurrencyPair("BTC/USD").setOpen(50500.0).setHigh(50500.0).setLow(50500.0).setClose(50500.0).setVolume(0.5).setTimestamp(Timestamps.fromMillis(t2.millis)).build()
        val expBtcWin3FF = Candle.newBuilder().setCurrencyPair("BTC/USD").setOpen(50500.0).setHigh(50500.0).setLow(50500.0).setClose(50500.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(win3End.millis)).build()
        // ETH: win1(actual), win2(fill-forward), win3(actual)
        val expEthWin1 = Candle.newBuilder().setCurrencyPair("ETH/USD").setOpen(2000.0).setHigh(2000.0).setLow(2000.0).setClose(2000.0).setVolume(2.0).setTimestamp(Timestamps.fromMillis(t1.millis)).build()
        val expEthWin2FF = Candle.newBuilder().setCurrencyPair("ETH/USD").setOpen(2000.0).setHigh(2000.0).setLow(2000.0).setClose(2000.0).setVolume(0.0).setTimestamp(Timestamps.fromMillis(win2End.millis)).build()
        val expEthWin3 = Candle.newBuilder().setCurrencyPair("ETH/USD").setOpen(2100.0).setHigh(2100.0).setLow(2100.0).setClose(2100.0).setVolume(1.5).setTimestamp(Timestamps.fromMillis(t3.millis)).build()


        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert
        // Check the entire PCollection content for all 6 expected candles
        PAssert.that(result.apply("ExtractValuesOnly", Values.create()))
            .containsInAnyOrder(
                expBtcWin1, expBtcWin2, expBtcWin3FF,
                expEthWin1, expEthWin2FF, expEthWin3
            )

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
