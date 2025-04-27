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
import org.hamcrest.MatcherAssert.assertThat
import org.hamcrest.Matchers.closeTo
import org.hamcrest.Matchers.equalTo

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
            .advanceWatermarkToInfinity()

        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<Candle>, Void?> {
            override fun apply(output: Iterable<Candle>): Void? {
                val candles = output.toList()
                assertThat("Should produce exactly one candle", candles.size, equalTo(1))
                
                val btcCandle = candles.first()
                assertThat("Currency pair should match", btcCandle.currencyPair, equalTo("BTC/USD"))
                assertThat("Open price should match", btcCandle.open, closeTo(50000.0, TOLERANCE))
                assertThat("High price should match", btcCandle.high, closeTo(50100.0, TOLERANCE))
                assertThat("Low price should match", btcCandle.low, closeTo(50000.0, TOLERANCE))
                assertThat("Close price should match", btcCandle.close, closeTo(50100.0, TOLERANCE))
                assertThat("Volume should match", btcCandle.volume, closeTo(1.5, TOLERANCE))
                assertThat("Timestamp seconds should match", btcCandle.timestamp.seconds, 
                           equalTo(Timestamps.fromMillis(t1.millis).seconds))
                
                return null
            }
        })

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
        
        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, baseTime.plus(Duration.standardSeconds(30))),
            baseTime.plus(Duration.standardSeconds(30))
        )

        // TestStream with trade in window 1, no trades in window 2
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Trade in window 1
            .advanceWatermarkTo(win1End.plus(Duration.standardSeconds(1))) // Trigger window 1 completion 
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1))) // Trigger window 2 completion
            .advanceWatermarkToInfinity()

        // Expected candle for window 1 (actual trades)
        val expectedCandleWin1 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(1.0)
            .setTimestamp(Timestamps.fromMillis(tradeWin1.timestamp.millis))
            .build()

        // Expected fill-forward candle for window 2
        val expectedFillForwardWin2 = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0) // Same as close from window 1
            .setHigh(50000.0)
            .setLow(50000.0)
            .setClose(50000.0)
            .setVolume(0.0) // Zero volume indicates fill-forward
            .setTimestamp(Timestamps.fromMillis(win2End.millis)) // Window 2 end time
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert - Should have both the original candle and the fill-forward candle
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<Candle>, Void?> {
            override fun apply(output: Iterable<Candle>): Void? {
                val candles = output.toList()
                
                assertThat("Should produce exactly two candles", candles.size, equalTo(2))
                
                // Find window 1 candle (has volume 1.0)
                val win1Candle = candles.first { it.volume > 0.0 }
                // Find window 2 candle (has volume 0.0)
                val win2Candle = candles.first { it.volume == 0.0 }
                
                // Check window 1 candle
                assertThat("Win1 volume should be 1.0", win1Candle.volume, closeTo(1.0, TOLERANCE))
                assertThat("Win1 close should be 50000.0", win1Candle.close, closeTo(50000.0, TOLERANCE))
                
                // Check window 2 candle (fill-forward)
                assertThat("Win2 volume should be 0.0", win2Candle.volume, closeTo(0.0, TOLERANCE))
                assertThat("Win2 close should match win1 close", win2Candle.close, closeTo(win1Candle.close, TOLERANCE))
                assertThat("Win2 all prices should be the same", win2Candle.open, equalTo(win2Candle.close))
                assertThat("Win2 all prices should be the same", win2Candle.high, equalTo(win2Candle.close))
                assertThat("Win2 all prices should be the same", win2Candle.low, equalTo(win2Candle.close))
                
                return null
            }
        })

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

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, baseTime.plus(Duration.standardSeconds(30))),
            baseTime.plus(Duration.standardSeconds(30))
        )

        // TestStream with trade in window 1, no trades in windows 2 and 3
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Trade in window 1
            .advanceWatermarkTo(win1End.plus(Duration.standardSeconds(1))) 
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkTo(win3End.plus(Duration.standardSeconds(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert - Should have 3 candles (1 actual, 2 fill-forward)
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<Candle>, Void?> {
            override fun apply(output: Iterable<Candle>): Void? {
                val candles = output.toList()
                
                assertThat("Should produce exactly three candles", candles.size, equalTo(3))
                
                // Count candles with zero volume (fill-forward)
                val fillForwardCandles = candles.filter { it.volume == 0.0 }
                assertThat("Should have 2 fill-forward candles", fillForwardCandles.size, equalTo(2))
                
                // Check all candles have same close price (propagated forward)
                val closePrices = candles.map { it.close }
                val allSamePrice = closePrices.all { Math.abs(it - closePrices[0]) < TOLERANCE }
                assertThat("All candles should have the same close price", allSamePrice, equalTo(true))
                
                return null
            }
        })

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
            .advanceWatermarkTo(win2End)
            .addElements(tradeWin3)
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<Candle>, Void?> {
            override fun apply(output: Iterable<Candle>): Void? {
                val candles = output.toList().sortedBy { it.timestamp.seconds }
                
                assertThat("Should produce exactly three candles", candles.size, equalTo(3))
                
                // First candle should be window 1 with actual trade
                val win1Candle = candles[0]
                assertThat("Win1 close should be 50000.0", win1Candle.close, closeTo(50000.0, TOLERANCE))
                assertThat("Win1 volume should be 1.0", win1Candle.volume, closeTo(1.0, TOLERANCE))
                
                // Second candle should be fill-forward in window 2
                val win2Candle = candles[1]
                assertThat("Win2 should be fill-forward with 0 volume", win2Candle.volume, closeTo(0.0, TOLERANCE))
                assertThat("Win2 close should match Win1 close", win2Candle.close, closeTo(win1Candle.close, TOLERANCE))
                
                // Third candle should be actual trade in window 3
                val win3Candle = candles[2]
                assertThat("Win3 close should be 51000.0", win3Candle.close, closeTo(51000.0, TOLERANCE))
                assertThat("Win3 volume should be 0.5", win3Candle.volume, closeTo(0.5, TOLERANCE))
                
                return null
            }
        })

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
        val ethWin3 = TimestampedValue.of(createTrade("ETH/USD", 2100.0, 1.5, t3), t3)

        // TestStream with different trade patterns for BTC and ETH
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(btcWin1, ethWin1) // Both in window 1
            .advanceWatermarkTo(win1End.plus(Duration.standardSeconds(1)))
            .addElements(btcWin2) // Only BTC in window 2
            .advanceWatermarkTo(win2End.plus(Duration.standardSeconds(1)))
            .addElements(ethWin3) // Only ETH in window 3
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Should produce 6 candles total", candles.size, equalTo(6))
                
                // Group by currency pair
                val btcCandles = candles.filter { it.key == "BTC/USD" }.map { it.value }
                          .sortedBy { it.timestamp.seconds }
                val ethCandles = candles.filter { it.key == "ETH/USD" }.map { it.value }
                          .sortedBy { it.timestamp.seconds }
                
                // Verify BTC candles (win1, win2, win3-fillforward)
                assertThat("Should have 3 BTC candles", btcCandles.size, equalTo(3))
                assertThat("Win1 BTC should have volume 1.0", btcCandles[0].volume, closeTo(1.0, TOLERANCE))
                assertThat("Win2 BTC should have volume 0.5", btcCandles[1].volume, closeTo(0.5, TOLERANCE))
                assertThat("Win3 BTC should be fill-forward", btcCandles[2].volume, closeTo(0.0, TOLERANCE))
                assertThat("Win3 BTC close should match Win2 close", 
                           btcCandles[2].close, closeTo(btcCandles[1].close, TOLERANCE))
                
                // Verify ETH candles (win1, win2-fillforward, win3)
                assertThat("Should have 3 ETH candles", ethCandles.size, equalTo(3))
                assertThat("Win1 ETH should have volume 2.0", ethCandles[0].volume, closeTo(2.0, TOLERANCE))
                assertThat("Win2 ETH should be fill-forward", ethCandles[1].volume, closeTo(0.0, TOLERANCE))
                assertThat("Win2 ETH close should match Win1 close",
                           ethCandles[1].close, closeTo(ethCandles[0].close, TOLERANCE))
                assertThat("Win3 ETH should have volume 1.5", ethCandles[2].volume, closeTo(1.5, TOLERANCE))
                
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
