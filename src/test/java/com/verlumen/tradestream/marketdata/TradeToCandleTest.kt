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
    @Transient // Avoids serialization issues with JUnit rules in Beam tests
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    @Inject
    lateinit var candleCreatorFn: CandleCreatorFn // Injected for Guice setup, used internally by TradeToCandle

    private val btcUsd = CurrencyPair.fromSymbol("BTC/USD")
    private val ethUsd = CurrencyPair.fromSymbol("ETH/USD")

    @Before
    fun setUp() {
        // Configure Guice for testing
        val testModule = BoundFieldModule.of(this) // Needed for @Inject fields in this test class
        val modules: List<Module> = listOf(
            testModule,
            object : AbstractModule() {
                override fun configure() {
                    // Ensure Guice knows about CandleCreatorFn for injection into TradeToCandle
                    bind(CandleCreatorFn::class.java)
                }
            },
            // Build the factory for TradeToCandle (which uses assisted injection)
            FactoryModuleBuilder()
                .implement(TradeToCandle::class.java, TradeToCandle::class.java)
                .build(TradeToCandle.Factory::class.java)
        )
        val injector = Guice.createInjector(modules)
        injector.injectMembers(this) // Inject dependencies into this test class (@Inject fields)
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
        val t1 = baseTime.plus(Duration.standardSeconds(15)) // 10:00:15 (first trade)
        val t2 = baseTime.plus(Duration.standardSeconds(45)) // 10:00:45 (last trade)

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, t1), t1
        )
        val tradeWin1Late = TimestampedValue.of(
            createTrade("BTC/USD", 50100.0, 0.5, t2), t2
        )

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1, tradeWin1Late)
            .advanceWatermarkToInfinity()

        // Expected candle uses the timestamp of the *first* trade
        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(t1.millis)) // Timestamp from first trade
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
                assertThat("Open price should match", btcCandle.open, closeTo(expectedBtcCandle.open, TOLERANCE))
                assertThat("High price should match", btcCandle.high, closeTo(expectedBtcCandle.high, TOLERANCE))
                assertThat("Low price should match", btcCandle.low, closeTo(expectedBtcCandle.low, TOLERANCE))
                assertThat("Close price should match", btcCandle.close, closeTo(expectedBtcCandle.close, TOLERANCE))
                assertThat("Volume should match", btcCandle.volume, closeTo(expectedBtcCandle.volume, TOLERANCE))
                // Compare timestamp seconds as nanos might differ slightly
                assertThat("Timestamp seconds should match", btcCandle.timestamp.seconds,
                           equalTo(expectedBtcCandle.timestamp.seconds))

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

        // Only BTC trades, no ETH trades ever
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Only BTC candle should exist, no ETH candle
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Should produce exactly one candle KV pair", candles.size, equalTo(1))
                assertThat("Should only contain BTC/USD key", candles[0].key, equalTo("BTC/USD"))
                // Check the candle itself
                val btcCandle = candles[0].value
                assertThat(btcCandle.open, closeTo(50000.0, TOLERANCE))
                assertThat(btcCandle.volume, closeTo(1.0, TOLERANCE))
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
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z") // Window 1: [10:00, 10:01)
        val win1End = baseTime.plus(windowDuration) // 10:01:00, End of Win 1, Start of Win 2
        val win2End = win1End.plus(windowDuration)  // 10:02:00, End of Win 2

        val tradeTimeWin1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, tradeTimeWin1),
            tradeTimeWin1
        )

        // TestStream with trade in window 1, no trades in window 2
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Trade in window 1 [10:00:00, 10:01:00)
            // Advance watermark past Win 1 end to trigger its processing
            .advanceWatermarkTo(win1End)
            // Advance watermark past Win 2 end to trigger its processing (should be fill-forward)
            .advanceWatermarkTo(win2End)
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<Candle> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)
            .apply("ExtractValues", Values.create())

        // Assert - Should have both the original candle and the fill-forward candle
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<Candle>, Void?> {
            override fun apply(output: Iterable<Candle>): Void? {
                val candles = output.toList().sortedBy { it.timestamp.seconds } // Sort by time

                assertThat("Should produce exactly two candles", candles.size, equalTo(2))

                // Check window 1 candle (actual trade)
                val win1Candle = candles[0]
                assertThat("Win1 Pair", win1Candle.currencyPair, equalTo("BTC/USD"))
                assertThat("Win1 Open", win1Candle.open, closeTo(50000.0, TOLERANCE))
                assertThat("Win1 Close", win1Candle.close, closeTo(50000.0, TOLERANCE))
                assertThat("Win1 Volume", win1Candle.volume, closeTo(1.0, TOLERANCE))
                assertThat("Win1 Timestamp", win1Candle.timestamp.seconds, equalTo(Timestamps.fromMillis(tradeTimeWin1.millis).seconds))

                // Check window 2 candle (fill-forward)
                val win2Candle = candles[1]
                assertThat("Win2 Pair", win2Candle.currencyPair, equalTo("BTC/USD"))
                assertThat("Win2 Volume should be 0.0", win2Candle.volume, closeTo(0.0, TOLERANCE))
                assertThat("Win2 Open should match win1 close", win2Candle.open, closeTo(win1Candle.close, TOLERANCE))
                assertThat("Win2 High should match win1 close", win2Candle.high, closeTo(win1Candle.close, TOLERANCE))
                assertThat("Win2 Low should match win1 close", win2Candle.low, closeTo(win1Candle.close, TOLERANCE))
                assertThat("Win2 Close should match win1 close", win2Candle.close, closeTo(win1Candle.close, TOLERANCE))
                // Fill-forward candle timestamp should be the end of the window it fills
                assertThat("Win2 Timestamp", win2Candle.timestamp.seconds, equalTo(Timestamps.fromMillis(win2End.millis).seconds))


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

        val tradeTimeWin1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30

        val tradeWin1 = TimestampedValue.of(
            createTrade("BTC/USD", 50000.0, 1.0, tradeTimeWin1),
            tradeTimeWin1
        )

        // TestStream with trade in window 1, no trades in windows 2 and 3
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Trade in window 1 [10:00, 10:01)
            .advanceWatermarkTo(win1End) // Trigger win 1 processing
            .advanceWatermarkTo(win2End) // Trigger win 2 processing (fill-forward)
            .advanceWatermarkTo(win3End) // Trigger win 3 processing (fill-forward)
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
                val candles = output.toList().sortedBy { it.timestamp.seconds }

                assertThat("Should produce exactly three candles", candles.size, equalTo(3))

                // Check counts
                val actualCandles = candles.filter { it.volume > 0.0 }
                val fillForwardCandles = candles.filter { it.volume == 0.0 }
                assertThat("Should have 1 actual candle", actualCandles.size, equalTo(1))
                assertThat("Should have 2 fill-forward candles", fillForwardCandles.size, equalTo(2))

                // Check prices are propagated
                val firstClose = candles[0].close
                assertThat("Win2 fill-forward close should match Win1 close", candles[1].close, closeTo(firstClose, TOLERANCE))
                assertThat("Win3 fill-forward close should match Win1 close", candles[2].close, closeTo(firstClose, TOLERANCE))

                // Check timestamps
                assertThat("Win1 Timestamp", candles[0].timestamp.seconds, equalTo(Timestamps.fromMillis(tradeTimeWin1.millis).seconds))
                assertThat("Win2 Timestamp", candles[1].timestamp.seconds, equalTo(Timestamps.fromMillis(win2End.millis).seconds))
                assertThat("Win3 Timestamp", candles[2].timestamp.seconds, equalTo(Timestamps.fromMillis(win3End.millis).seconds))


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

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30 (Win 1)
        val t3 = win2End.plus(Duration.standardSeconds(30))  // 10:02:30 (Win 3)

        val tradeWin1 = TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
        val tradeWin3 = TimestampedValue.of(createTrade("BTC/USD", 51000.0, 0.5, t3), t3)

        // TestStream with trades in windows 1 and 3, no trades in window 2
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1) // Win 1 [10:00, 10:01)
            .advanceWatermarkTo(win1End) // Trigger Win 1
            // No trades for Win 2 [10:01, 10:02)
            .advanceWatermarkTo(win2End) // Trigger Win 2 (fill-forward)
            .addElements(tradeWin3) // Win 3 [10:02, 10:03)
            .advanceWatermarkTo(win3End) // Trigger Win 3
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

                // First candle: Actual trade in window 1
                val win1Candle = candles[0]
                assertThat("Win1 close", win1Candle.close, closeTo(50000.0, TOLERANCE))
                assertThat("Win1 volume", win1Candle.volume, closeTo(1.0, TOLERANCE))
                assertThat("Win1 Timestamp", win1Candle.timestamp.seconds, equalTo(Timestamps.fromMillis(t1.millis).seconds))


                // Second candle: Fill-forward in window 2
                val win2Candle = candles[1]
                assertThat("Win2 should be fill-forward", win2Candle.volume, closeTo(0.0, TOLERANCE))
                assertThat("Win2 close should match Win1 close", win2Candle.close, closeTo(win1Candle.close, TOLERANCE))
                assertThat("Win2 Timestamp", win2Candle.timestamp.seconds, equalTo(Timestamps.fromMillis(win2End.millis).seconds))


                // Third candle: Actual trade in window 3
                val win3Candle = candles[2]
                assertThat("Win3 close", win3Candle.close, closeTo(51000.0, TOLERANCE))
                assertThat("Win3 volume", win3Candle.volume, closeTo(0.5, TOLERANCE))
                 assertThat("Win3 Timestamp", win3Candle.timestamp.seconds, equalTo(Timestamps.fromMillis(t3.millis).seconds))


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

        // Timestamps for trades
        val t1a = baseTime.plus(Duration.standardSeconds(20)) // 10:00:20 (Win 1)
        val t1b = baseTime.plus(Duration.standardSeconds(40)) // 10:00:40 (Win 1)
        val t2 = win1End.plus(Duration.standardSeconds(30))  // 10:01:30 (Win 2)
        val t3 = win2End.plus(Duration.standardSeconds(30))  // 10:02:30 (Win 3)

        // Trades
        val btcWin1a = TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1a), t1a)
        val ethWin1b = TimestampedValue.of(createTrade("ETH/USD", 2000.0, 2.0, t1b), t1b)
        val btcWin2 = TimestampedValue.of(createTrade("BTC/USD", 50500.0, 0.5, t2), t2) // Only BTC in Win 2
        val ethWin3 = TimestampedValue.of(createTrade("ETH/USD", 2100.0, 1.5, t3), t3) // Only ETH in Win 3

        // TestStream:
        // Win 1: BTC and ETH trades
        // Win 2: Only BTC trade (ETH should fill-forward)
        // Win 3: Only ETH trade (BTC should fill-forward)
        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(btcWin1a, ethWin1b) // Win 1 [10:00, 10:01)
            .advanceWatermarkTo(win1End) // Trigger Win 1
            .addElements(btcWin2) // Win 2 [10:01, 10:02)
            .advanceWatermarkTo(win2End) // Trigger Win 2
            .addElements(ethWin3) // Win 3 [10:02, 10:03)
            .advanceWatermarkTo(win3End) // Trigger Win 3
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
                assertThat("Should produce 6 candles total (3 BTC, 3 ETH)", candles.size, equalTo(6))

                // Group by currency pair and sort by time
                val btcCandles = candles.filter { it.key == "BTC/USD" }.map { it.value }
                          .sortedBy { it.timestamp.seconds }
                val ethCandles = candles.filter { it.key == "ETH/USD" }.map { it.value }
                          .sortedBy { it.timestamp.seconds }

                // Verify BTC candles (win1-actual, win2-actual, win3-fillforward)
                assertThat("Should have 3 BTC candles", btcCandles.size, equalTo(3))
                assertThat("Win1 BTC Volume", btcCandles[0].volume, closeTo(1.0, TOLERANCE))
                assertThat("Win1 BTC Close", btcCandles[0].close, closeTo(50000.0, TOLERANCE))
                assertThat("Win1 BTC Timestamp", btcCandles[0].timestamp.seconds, equalTo(Timestamps.fromMillis(t1a.millis).seconds))

                assertThat("Win2 BTC Volume", btcCandles[1].volume, closeTo(0.5, TOLERANCE))
                assertThat("Win2 BTC Close", btcCandles[1].close, closeTo(50500.0, TOLERANCE))
                assertThat("Win2 BTC Timestamp", btcCandles[1].timestamp.seconds, equalTo(Timestamps.fromMillis(t2.millis).seconds))


                assertThat("Win3 BTC should be fill-forward", btcCandles[2].volume, closeTo(0.0, TOLERANCE))
                assertThat("Win3 BTC close should match Win2 BTC close",
                           btcCandles[2].close, closeTo(btcCandles[1].close, TOLERANCE)) // Fills from BTC Win 2
                assertThat("Win3 BTC Timestamp", btcCandles[2].timestamp.seconds, equalTo(Timestamps.fromMillis(win3End.millis).seconds))


                // Verify ETH candles (win1-actual, win2-fillforward, win3-actual)
                assertThat("Should have 3 ETH candles", ethCandles.size, equalTo(3))
                assertThat("Win1 ETH Volume", ethCandles[0].volume, closeTo(2.0, TOLERANCE))
                assertThat("Win1 ETH Close", ethCandles[0].close, closeTo(2000.0, TOLERANCE))
                assertThat("Win1 ETH Timestamp", ethCandles[0].timestamp.seconds, equalTo(Timestamps.fromMillis(t1b.millis).seconds))


                assertThat("Win2 ETH should be fill-forward", ethCandles[1].volume, closeTo(0.0, TOLERANCE))
                assertThat("Win2 ETH close should match Win1 ETH close",
                           ethCandles[1].close, closeTo(ethCandles[0].close, TOLERANCE)) // Fills from ETH Win 1
                assertThat("Win2 ETH Timestamp", ethCandles[1].timestamp.seconds, equalTo(Timestamps.fromMillis(win2End.millis).seconds))


                assertThat("Win3 ETH Volume", ethCandles[2].volume, closeTo(1.5, TOLERANCE))
                assertThat("Win3 ETH Close", ethCandles[2].close, closeTo(2100.0, TOLERANCE))
                assertThat("Win3 ETH Timestamp", ethCandles[2].timestamp.seconds, equalTo(Timestamps.fromMillis(t3.millis).seconds))


                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    // Helper to create trade objects more easily
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
            .setExchange("TEST") // Just a test exchange
            .setTradeId("test-${timestamp.millis}-${System.nanoTime()}") // Unique-ish ID
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .build()
    }
}
