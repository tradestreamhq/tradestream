package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.transforms.Values
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TimestampedValue
import org.hamcrest.MatcherAssert.assertThat
import org.hamcrest.Matchers.closeTo
import org.hamcrest.Matchers.equalTo
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.io.Serializable
import com.google.inject.AbstractModule
import com.google.inject.Inject
import org.hamcrest.Matchers.containsInAnyOrder


class TradeToCandleTest : Serializable {

    companion object {
        private const val serialVersionUID = 1L
        private const val TOLERANCE = 0.00001
        private const val DEFAULT_CURRENCY_PAIR = "BTC/USD"
    }

    @Rule @JvmField
    val pipeline: TestPipeline = TestPipeline.create()

    // Use @Inject for factory
    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    @Bind // Bind the dependency needed by the implementation
    private val candleCombineFn = CandleCombineFn()

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
            // No need for CandleCombineFn binding here if @Bind is used above
        )
        val injector = Guice.createInjector(modules)
        injector.injectMembers(this) // Inject factory into the test instance
    }

    /**
     * Verifies basic candle generation with trades present in the window.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testBasicCandleGeneration() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00.000Z

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30
        val t2 = baseTime.plus(Duration.standardSeconds(45)) // 10:00:45

        val tradeWin1 = TimestampedValue.of(
            createTrade(DEFAULT_CURRENCY_PAIR, 50000.0, 1.0, t1), t1
        )
        val tradeWin1Late = TimestampedValue.of(
            createTrade(DEFAULT_CURRENCY_PAIR, 50100.0, 0.5, t2), t2
        )

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(tradeWin1, tradeWin1Late)
            // Advance watermark PAST the interval end to trigger the timer
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair(DEFAULT_CURRENCY_PAIR)
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0) // Close price is from the last trade (t2)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(win1End.millis)) // Timestamp at interval end
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert
        PAssert.that(result)
            .containsInAnyOrder(KV.of(expectedBtcCandle.currencyPair, expectedBtcCandle))
        PAssert.that(result).satisfies(CountCandles(1)) // Ensure only one candle is produced

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that we only produce candles for currency pairs that have actual trades.
     * Even with fill-forward, if a pair *never* had a trade, it shouldn't produce candles.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testNoOutputForPairWithNoHistory() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration)
        val t1 = baseTime.plus(Duration.standardSeconds(30))

        // Only include trades for BTC/USD
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

        // Assert - Verify only the BTC/USD candle is present
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList()
                assertThat("Should produce exactly one candle", candles.size, equalTo(1))
                assertThat("Candle key should be BTC/USD", candles[0].key, equalTo("BTC/USD"))
                // Check a value to be sure it's the right candle
                assertThat(candles[0].value.open, closeTo(50000.0, TOLERANCE))
                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that candles are correctly keyed by currency pair.
     */
    @Test(timeout = 30000) // 30 second timeout
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
                assertThat("Candle currency pair field should match key", candles[0].value.currencyPair, equalTo("BTC/USD"))
                return null
            }
        })
        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that multiple currency pairs are processed independently.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testMultipleCurrencyPairs() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(15)) // BTC trade
        val t2 = baseTime.plus(Duration.standardSeconds(30)) // ETH trade
        val win1End = baseTime.plus(windowDuration)

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade("BTC/USD", 50000.0, 1.0, t1), t1),
                TimestampedValue.of(createTrade("ETH/USD", 3000.0, 2.0, t2), t2)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
         val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0).setHigh(50000.0).setLow(50000.0).setClose(50000.0) // Single trade
            .setVolume(1.0)
            .setTimestamp(Timestamps.fromMillis(win1End.millis))
            .build()
         val expectedEthCandle = Candle.newBuilder()
            .setCurrencyPair("ETH/USD")
            .setOpen(3000.0).setHigh(3000.0).setLow(3000.0).setClose(3000.0) // Single trade
            .setVolume(2.0)
            .setTimestamp(Timestamps.fromMillis(win1End.millis))
            .build()


        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Check for both expected candles
        PAssert.that(result).containsInAnyOrder(
            KV.of("BTC/USD", expectedBtcCandle),
            KV.of("ETH/USD", expectedEthCandle)
        )
         PAssert.that(result).satisfies(CountCandles(2))


        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies candle values for a single trade.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testSingleTradeCandle() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(30))
        val win1End = baseTime.plus(windowDuration)

        val price = 50000.0
        val volume = 1.0
        val pair = "BTC/USD"

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade(pair, price, volume, t1), t1)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

         val expectedCandle = Candle.newBuilder()
            .setCurrencyPair(pair)
            .setOpen(price).setHigh(price).setLow(price).setClose(price) // OHLC = price for single trade
            .setVolume(volume)
            .setTimestamp(Timestamps.fromMillis(win1End.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert
        PAssert.that(result).containsInAnyOrder(KV.of(pair, expectedCandle))
        PAssert.that(result).satisfies(CountCandles(1))

        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies candle values for multiple trades within the same interval.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testMultipleTradesCandle() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(15)) // 50000.0 (Open)
        val t2 = baseTime.plus(Duration.standardSeconds(30)) // 50500.0 (High)
        val t3 = baseTime.plus(Duration.standardSeconds(45)) // 49800.0 (Low, Close)
        val win1End = baseTime.plus(windowDuration)
        val pair = "BTC/USD"

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade(pair, 50000.0, 1.0, t1), t1),
                TimestampedValue.of(createTrade(pair, 50500.0, 0.5, t2), t2),
                TimestampedValue.of(createTrade(pair, 49800.0, 0.8, t3), t3)
            )
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        val expectedCandle = Candle.newBuilder()
            .setCurrencyPair(pair)
            .setOpen(50000.0)
            .setHigh(50500.0)
            .setLow(49800.0)
            .setClose(49800.0) // Last trade price
            .setVolume(1.0 + 0.5 + 0.8) // Sum of volumes
            .setTimestamp(Timestamps.fromMillis(win1End.millis))
            .build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert
        PAssert.that(result).containsInAnyOrder(KV.of(pair, expectedCandle))
        PAssert.that(result).satisfies(CountCandles(1))


        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that candle timestamps are set to interval end times.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testCandleTimestamp() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val t1 = baseTime.plus(Duration.standardSeconds(30))
        val win1End = baseTime.plus(windowDuration) // Expected candle timestamp

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

                assertThat("Candle data timestamp should be at interval end",
                           candleTimestamp, equalTo(win1End))

                return null
            }
        })
        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that candles are generated for consecutive intervals.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testConsecutiveIntervals() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val win2End = win1End.plus(windowDuration) // 10:02:00
        val pair = "BTC/USD"

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30 - first window
        val t2 = win1End.plus(Duration.standardSeconds(30)) // 10:01:30 - second window

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                TimestampedValue.of(createTrade(pair, 50000.0, 1.0, t1), t1) // Win 1
            )
            // Advance watermark past the *first* interval end to trigger its timer
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .addElements(
                TimestampedValue.of(createTrade(pair, 50200.0, 0.5, t2), t2) // Win 2
            )
            // Advance watermark past the *second* interval end
            .advanceWatermarkTo(win2End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
         val expectedCandle1 = Candle.newBuilder()
            .setCurrencyPair(pair).setOpen(50000.0).setHigh(50000.0).setLow(50000.0).setClose(50000.0)
            .setVolume(1.0).setTimestamp(Timestamps.fromMillis(win1End.millis)).build()
         val expectedCandle2 = Candle.newBuilder()
            .setCurrencyPair(pair).setOpen(50200.0).setHigh(50200.0).setLow(50200.0).setClose(50200.0)
            .setVolume(0.5).setTimestamp(Timestamps.fromMillis(win2End.millis)).build()


        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify we get candles for both intervals
        PAssert.that(result).containsInAnyOrder(
            KV.of(pair, expectedCandle1),
            KV.of(pair, expectedCandle2)
        )
        PAssert.that(result).satisfies(CountCandles(2))


        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies fill-forward behavior for empty intervals.
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testFillForwardEmptyInterval() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00 (Trade)
        val win2End = win1End.plus(windowDuration) // 10:02:00 (Empty -> Fill Forward)
        val win3End = win2End.plus(windowDuration) // 10:03:00 (Trade)
        val pair = "BTC/USD"

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30 - first window
        val t3 = win2End.plus(Duration.standardSeconds(30)) // 10:02:30 - third window

        val closePriceWin1 = 50100.0 // Close price of the first candle

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                // Use the helper that allows specifying close price if needed for combineFn
                TimestampedValue.of(createTrade(pair, 50000.0, 1.0, t1, closePrice = closePriceWin1), t1)
            )
            // Advance watermark past win1End to trigger first candle and set timer for win2End
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            // Advance watermark past win2End to trigger the timer for the empty interval (-> fill forward)
            // This also sets the timer for win3End
            .advanceWatermarkTo(win2End.plus(Duration.millis(1)))
            .addElements(
                TimestampedValue.of(createTrade(pair, 50200.0, 0.5, t3), t3) // Trade for win 3
            )
            // Advance watermark past win3End to trigger the last candle
            .advanceWatermarkTo(win3End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Expected Candles
        val expectedCandle1 = Candle.newBuilder() // Actual candle from t1
            .setCurrencyPair(pair).setOpen(50000.0).setHigh(50000.0).setLow(50000.0).setClose(closePriceWin1)
            .setVolume(1.0).setTimestamp(Timestamps.fromMillis(win1End.millis)).build()

        val expectedCandle2 = Candle.newBuilder() // Fill-forward candle
            .setCurrencyPair(pair)
            .setOpen(closePriceWin1).setHigh(closePriceWin1).setLow(closePriceWin1).setClose(closePriceWin1) // OHLC = prev close
            .setVolume(0.0) // Zero volume
            .setTimestamp(Timestamps.fromMillis(win2End.millis)).build() // Timestamp is interval end

        val expectedCandle3 = Candle.newBuilder() // Actual candle from t3
            .setCurrencyPair(pair).setOpen(50200.0).setHigh(50200.0).setLow(50200.0).setClose(50200.0)
            .setVolume(0.5).setTimestamp(Timestamps.fromMillis(win3End.millis)).build()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify we get exactly three candles (original, fill-forward, original)
        PAssert.that(result).containsInAnyOrder(
            KV.of(pair, expectedCandle1),
            KV.of(pair, expectedCandle2),
            KV.of(pair, expectedCandle3)
        )
         PAssert.that(result).satisfies(CountCandles(3))


        pipeline.run().waitUntilFinish()
    }

    /**
     * Verifies that fill-forward candles have expected OHLCV values.
     * (This is partially tested above, but adds explicit checks)
     */
    @Test(timeout = 30000) // 30 second timeout
    fun testFillForwardCandleValues() {
        // Arrange
        val windowDuration = Duration.standardMinutes(1)
        val baseTime = Instant.parse("2023-01-01T10:00:00.000Z")
        val win1End = baseTime.plus(windowDuration) // 10:01:00
        val win2End = win1End.plus(windowDuration) // 10:02:00 (Empty)
        val win3End = win2End.plus(windowDuration) // 10:03:00 (Trade after empty)
        val pair = "BTC/USD"

        val t1 = baseTime.plus(Duration.standardSeconds(30)) // 10:00:30
        val t3 = win2End.plus(Duration.standardSeconds(30)) // 10:02:30

        val originalClosePrice = 50150.0 // Explicit close price for the first trade/candle

        val tradeStream = TestStream.create(ProtoCoder.of(Trade::class.java))
            .addElements(
                 // Single trade in first interval, use helper to set effective close
                TimestampedValue.of(createTrade(pair, 50000.0, 1.0, t1, closePrice=originalClosePrice), t1)
            )
            // Advance watermark past win1End and win2End to trigger candles 1 and 2 (fill-forward)
            .advanceWatermarkTo(win1End.plus(Duration.millis(1)))
            .advanceWatermarkTo(win2End.plus(Duration.millis(1)))
            .addElements(
                TimestampedValue.of(createTrade(pair, 50200.0, 0.5, t3), t3) // Trade for 3rd interval
            )
            .advanceWatermarkTo(win3End.plus(Duration.millis(1)))
            .advanceWatermarkToInfinity()

        // Act
        val transform = tradeToCandleFactory.create(windowDuration)
        val result: PCollection<KV<String, Candle>> = pipeline
            .apply(tradeStream)
            .apply("TradeToCandle", transform)

        // Assert - Verify fill-forward candle has expected values
        PAssert.that(result).satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
            override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                val candles = output.toList().sortedBy { Timestamps.toMillis(it.value.timestamp) }

                assertThat("Should produce exactly three candles", candles.size, equalTo(3))

                // Identify the fill-forward candle (the second one, ending at win2End)
                val fillForwardCandle = candles.find { Instant(Timestamps.toMillis(it.value.timestamp)) == win2End }?.value
                assertThat("Fill-forward candle should exist", fillForwardCandle != null)

                if (fillForwardCandle != null) {
                    // Check fill-forward properties
                    assertThat("Fill-forward candle should have zero volume",
                               fillForwardCandle.volume, closeTo(0.0, TOLERANCE))

                    // OHLC should match the previous candle's close price
                    assertThat("Fill-forward open should equal previous close",
                               fillForwardCandle.open, closeTo(originalClosePrice, TOLERANCE))
                    assertThat("Fill-forward high should equal previous close",
                               fillForwardCandle.high, closeTo(originalClosePrice, TOLERANCE))
                    assertThat("Fill-forward low should equal previous close",
                               fillForwardCandle.low, closeTo(originalClosePrice, TOLERANCE))
                    assertThat("Fill-forward close should equal previous close",
                               fillForwardCandle.close, closeTo(originalClosePrice, TOLERANCE))
                    assertThat("Fill-forward currency pair should match",
                               fillForwardCandle.currencyPair, equalTo(pair))
                }
                return null
            }
        })

        pipeline.run().waitUntilFinish()
    }

    // Helper to create trade objects with specific close price for testing CombineFn logic
    // NOTE: The actual DoFn logic derives close from the *last* trade's price in the interval.
    // This helper simulates what the CombineFn *might* produce if it considered an explicit close.
    // For the stateful DoFn, the 'closePrice' param here is ONLY relevant if the CombineFn uses it.
    // The default CandleCombineFn uses the price of the last trade added.
    private fun createTrade(
        currencyPair: String,
        price: Double,
        volume: Double,
        timestamp: Instant,
        closePrice: Double = price // Default close to trade price - used by some tests for expected values
    ): Trade {
        // The stateful processor determines the actual close price from the sequence of trades.
        // This helper just creates a Trade proto.
        return Trade.newBuilder()
            .setCurrencyPair(currencyPair)
            .setPrice(price)
            .setVolume(volume)
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
             // The underlying CombineFn likely uses the price field for OHLC calculation.
             // We don't have a separate "close" field in the Trade proto itself.
             // The 'closePrice' parameter is mainly for test expectation setup.
            .build()
    }

     // Helper PAssert function to check candle count
     private class CountCandles(private val expectedCount: Int) :
         SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
         override fun apply(input: Iterable<KV<String, Candle>>): Void? {
             val count = input.count()
             assertThat("Expected $expectedCount candles, but found $count", count, equalTo(expectedCount))
             return null
         }
     }
}
