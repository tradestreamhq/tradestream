package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.transforms.Values
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TimestampedValue
import org.apache.beam.sdk.values.TypeDescriptor
import org.hamcrest.MatcherAssert.assertThat
import org.hamcrest.Matchers.closeTo
import org.hamcrest.Matchers.equalTo
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.io.Serializable

class TradeToCandleTest : Serializable {

    companion object {
        private const val serialVersionUID = 1L
        private const val TOLERANCE = 0.00001
        private const val DEFAULT_CURRENCY_PAIR = "BTC/USD"
    }

    @Rule
    @JvmField
    @Transient
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    @Bind
    private val candleCombineFn = CandleCombineFn()

    @Before
    fun setUp() {
        // Configure Guice for testing
        val testModule = BoundFieldModule.of(this)
        val modules: List<Module> = listOf(
            testModule,
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
            createTrade(DEFAULT_CURRENCY_PAIR, 50000.0, 1.0, t1), t1
        )
        val tradeWin1Late = TimestampedValue.of(
            createTrade(DEFAULT_CURRENCY_PAIR, 50100.0, 0.5, t2), t2
        )

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1, tradeWin1Late)
            .advanceWatermarkTo(win1End.plus(Duration.millis(1))) // Ensure window closes
            .advanceWatermarkToInfinity()

        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair(DEFAULT_CURRENCY_PAIR)
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(win1End.millis)) // Timestamp at interval end
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
     * Verifies that we only produce candles for currency pairs that have actual trades.
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
                assertThat("Candle key should be BTC/USD", candles[0].key, equalTo("BTC/USD"))
                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that candles are correctly keyed by currency pair.
     */
    @Test
    fun testCandleKeying() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(30))
        val win1End = baseTime.plus(windowDuration)

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify the candle is keyed by currency pair
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Candle list should not be empty", candles.isNotEmpty(), equalTo(true))
                assertThat("Candle should be keyed by currency pair", candles[0].key, equalTo("BTC/USD"))
                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that multiple currency pairs are processed independently.
     */
    @Test
    fun testMultipleCurrencyPairs() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(15))
        val t2 = baseTime.plus(Duration.standardSeconds(30))
        val win1End = baseTime.plus(windowDuration)

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1),
                TimestampedValue.of(createTrade("ETH/USD", 3000.0, 2.0, t2), t2)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Count of candles should be 2 (one for each currency pair)
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Should produce one candle per currency pair", candles.size, equalTo(2))
                assertThat("Should contain BTC/USD candle", candles.any { it.key == "BTC/USD" }, equalTo(true))
                assertThat("Should contain ETH/USD candle", candles.any { it.key == "ETH/USD" }, equalTo(true))
                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies candle values for a single trade.
     */
    @Test
    fun testSingleTradeCandle() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(30))
        val win1End = baseTime.plus(windowDuration)

        val price = 50000.0
        val volume = 1.0

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", price, volume, t1), t1)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify OHLCV values for a single trade candle
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Output should not be empty", candles.isNotEmpty(), equalTo(true))
                val candle = candles.first().value

                // For a single trade, OHLC should all be the same price
                assertThat("Open price should match trade price", candle.open, closeTo(price, TOLERANCE))
                assertThat("High price should match trade price", candle.high, closeTo(price, TOLERANCE))
                assertThat("Low price should match trade price", candle.low, closeTo(price, TOLERANCE))
                assertThat("Close price should match trade price", candle.close, closeTo(price, TOLERANCE))
                assertThat("Volume should match trade volume", candle.volume, closeTo(volume, TOLERANCE))

                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies candle values for multiple trades within the same interval.
     */
    @Test
    fun testMultipleTradesCandle() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(15))
        val t2 = baseTime.plus(Duration.standardSeconds(30))
        val t3 = baseTime.plus(Duration.standardSeconds(45))
        val win1End = baseTime.plus(windowDuration)

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1),
                TimestampedValue.of(createTrade("BTC/USD", 50500.0, 0.5, t2), t2),
                TimestampedValue.of(createTrade("BTC/USD", 49800.0, 0.8, t3), t3)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify OHLCV values are correctly aggregated
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Output should not be empty", candles.isNotEmpty(), equalTo(true))
                val candle = candles.first().value

                assertThat("Open should be first trade price", candle.open, closeTo(50000.0, TOLERANCE))
                assertThat("High should be highest trade price", candle.high, closeTo(50500.0, TOLERANCE))
                assertThat("Low should be lowest trade price", candle.low, closeTo(49800.0, TOLERANCE))
                assertThat("Close should be last trade price", candle.close, closeTo(49800.0, TOLERANCE))
                assertThat("Volume should be sum of all trade volumes", candle.volume, closeTo(2.3, TOLERANCE))

                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that candle timestamps are set to interval end times.
     */
    @Test
    fun testCandleTimestamp() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(30))
        val win1End = baseTime.plus(windowDuration)

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify candle timestamp is set to interval end
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Output should not be empty", candles.isNotEmpty(), equalTo(true))
                val candle = candles.first().value
                val candleTimestamp = Instant(Timestamps.toMillis(candle.timestamp))

                assertThat("Candle timestamp should be at interval end",
                           candleTimestamp, equalTo(win1End))

                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that candles are generated for consecutive intervals.
     */
    @Test
    fun testConsecutiveIntervals() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val win2End = win1End.plus(windowDuration) // 10:02:00

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30 - first window
        val t2 = win1End.plus(Duration.standardSeconds(30)) // 10:01:30 - second window

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
            .advanceWatermarkTo(t2) // Advance watermark to trigger first window
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50200.0, 0.5, t2), t2)
            )
            .advanceWatermarkTo(win2End.plus(Duration.millis(1))) // Advance past second window
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify we get candles for both intervals
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Should produce exactly two candles (one per interval)",
                           candles.size, equalTo(2))

                val timestamps = candles.map { Instant(Timestamps.toMillis(it.value.timestamp)) }
                assertThat(timestamps).containsExactly(win1End, win2End)

                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies fill-forward behavior for empty intervals.
     */
    @Test
    fun testFillForwardEmptyInterval() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val win2End = win1End.plus(windowDuration) // 10:02:00
        val win3End = win2End.plus(windowDuration) // 10:03:00

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30 - first window
        val t3 = win2End.plus(Duration.standardSeconds(30)) // 10:02:30 - third window

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1)
            )
            .advanceWatermarkTo(win2End) // Advance watermark past second window (empty interval)
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50200.0, 0.5, t3), t3)
            )
            .advanceWatermarkTo(win3End.plus(Duration.millis(1))) // Advance past third window
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration, 3) // Allow fill-forward
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify we get exactly three candles (original, fill-forward, original)
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList().sortedBy { Timestamps.toMillis(it.value.timestamp) }
                assertThat("Should produce exactly three candles including fill-forward",
                           candles.size, equalTo(3))

                val timestamps = candles.map { Instant(Timestamps.toMillis(it.value.timestamp)) }
                assertThat(timestamps).containsExactly(win1End, win2End, win3End).inOrder()

                // Verify fill-forward candle (index 1)
                val fillForwardCandle = candles[1].value
                assertThat("Fill-forward candle should have zero volume",
                           fillForwardCandle.volume, closeTo(0.0, TOLERANCE))
                assertThat("Fill-forward candle OHLC should match previous close",
                           fillForwardCandle.close, closeTo(candles[0].value.close, TOLERANCE))

                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that fill-forward candles have expected OHLCV values.
     */
    @Test
    fun testFillForwardCandleValues() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val win2End = win1End.plus(windowDuration) // 10:02:00
        val win3End = win2End.plus(windowDuration) // 10:03:00

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30 - first window
        val t3 = win2End.plus(Duration.standardSeconds(30)) // 10:02:30 - third window

        val originalClosePrice = 50150.0 // Close price of the first candle

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1, originalClosePrice), t1)
            )
            .advanceWatermarkTo(win2End) // Advance watermark past second window
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50200.0, 0.5, t3), t3)
            )
            .advanceWatermarkTo(win3End.plus(Duration.millis(1))) // Advance past third window
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration, 3) // Allow fill-forward
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify fill-forward candle has expected values
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList().sortedBy { Timestamps.toMillis(it.value.timestamp) }
                assertThat("Should produce exactly three candles", candles.size, equalTo(3))

                // Second candle should be fill-forward
                val fillForwardCandle = candles[1].value
                assertThat("Fill-forward candle should have zero volume",
                           fillForwardCandle.volume, closeTo(0.0, TOLERANCE))

                // All OHLC values should be equal to the previous close
                assertThat("Fill-forward open should equal previous close",
                           fillForwardCandle.open, closeTo(originalClosePrice, TOLERANCE))
                assertThat("Fill-forward high should equal previous close",
                           fillForwardCandle.high, closeTo(originalClosePrice, TOLERANCE))
                assertThat("Fill-forward low should equal previous close",
                           fillForwardCandle.low, closeTo(originalClosePrice, TOLERANCE))
                assertThat("Fill-forward close should equal previous close",
                           fillForwardCandle.close, closeTo(originalClosePrice, TOLERANCE))

                // Verify timestamp
                assertThat("Fill-forward timestamp should be win2End",
                    Instant(Timestamps.toMillis(fillForwardCandle.timestamp)), equalTo(win2End))

                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }


    // Helper to create trade objects with specific close price
    private fun createTrade(
        currencyPair: String,
        price: Double,
        volume: Double,
        timestamp: Instant,
        closePrice: Double = price // Default close to trade price
    ): Trade {
        return Trade.newBuilder()
            .setCurrencyPair(currencyPair)
            .setPrice(price)
            .setVolume(volume)
            .setExchange("TEST")
            .setTradeId("test-${timestamp.millis}-${System.nanoTime()}")
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            // Set other fields if needed for Candle generation (e.g., open/high/low based on `price`)
            // For simplicity here, assuming CandleCombineFn mainly uses price and timestamp
            .build()
    }
     // Overload without close price, for compatibility with existing tests
     private fun createTrade(
        currencyPair: String,
        price: Double,
        volume: Double,
        timestamp: Instant
    ): Trade {
        return createTrade(currencyPair, price, volume, timestamp, price)
    }
}
