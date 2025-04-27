package com.verlumen.tradestream.marketdata

import com.google.common.base.Suppliers
import com.google.common.collect.ImmutableList
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.time.Instant
import java.util.function.Supplier
import java.io.Serializable
import com.google.protobuf.util.Timestamps
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.values.TimestampedValue
import com.google.protobuf.Timestamp
import com.google.inject.AbstractModule  // Import AbstractModule

// Make assertions in a serializable helper
class CandleChecker(
    private val expectedBtcCandle: Candle?,
    private val expectedEthCandle: Candle?,
    private val testName: String // Add test name for better logging
) : SerializableFunction<Iterable<KV<String, Candle>>, Void?>, Serializable {

    companion object {
        private const val serialVersionUID = 1L
        private const val tolerance = 0.00001
    }

    override fun apply(output: Iterable<KV<String, Candle>>): Void? {
        val candles = output.toList().associate { it.key to it.value }
        val expectedCount = listOfNotNull(expectedBtcCandle, expectedEthCandle).size

        // Check count first
        assert(candles.size == expectedCount) {
             "$testName: Expected $expectedCount candles (${listOfNotNull(expectedBtcCandle?.currencyPair, expectedEthCandle?.currencyPair).joinToString()}), found ${candles.size}: ${candles.keys}"
        }

        // Check BTC candle if expected
        if (expectedBtcCandle != null) {
            val btcCandle = candles["BTC/USD"]
            assert(btcCandle != null) { "$testName: Missing BTC/USD candle" }
            assertCandle(expectedBtcCandle, btcCandle!!, testName)
        }

        // Check ETH candle if expected
        if (expectedEthCandle != null) {
            val ethCandle = candles["ETH/USD"]
            assert(ethCandle != null) { "$testName: Missing ETH/USD candle (was expecting default?)" }
            assertCandle(expectedEthCandle, ethCandle!!, testName, true) // Check timestamp for default
        }

        return null
    }

    private fun assertCandle(expected: Candle, actual: Candle, testName: String, checkTimestampSecs: Boolean = true) {
        assert(expected.currencyPair == actual.currencyPair) {
            "$testName: Currency pair mismatch for ${actual.currencyPair}: Expected ${expected.currencyPair}, got ${actual.currencyPair}"
        }
        assert(kotlin.math.abs(expected.open - actual.open) < tolerance) {
            "$testName: Open price mismatch for ${actual.currencyPair}: Expected ${expected.open}, got ${actual.open}"
        }
        assert(kotlin.math.abs(expected.high - actual.high) < tolerance) {
            "$testName: High price mismatch for ${actual.currencyPair}: Expected ${expected.high}, got ${actual.high}"
        }
        assert(kotlin.math.abs(expected.low - actual.low) < tolerance) {
            "$testName: Low price mismatch for ${actual.currencyPair}: Expected ${expected.low}, got ${actual.low}"
        }
        assert(kotlin.math.abs(expected.close - actual.close) < tolerance) {
            "$testName: Close price mismatch for ${actual.currencyPair}: Expected ${expected.close}, got ${actual.close}"
        }
        assert(kotlin.math.abs(expected.volume - actual.volume) < tolerance) {
            "$testName: Volume mismatch for ${actual.currencyPair}: Expected ${expected.volume}, got ${actual.volume}"
        }
        // Timestamp check: Use seconds for comparison as nanos might differ slightly due to internal mechanics or Joda/Proto conversion
        if (checkTimestampSecs) {
             assert(expected.timestamp.seconds == actual.timestamp.seconds) {
                "$testName: Timestamp mismatch (seconds) for ${actual.currencyPair}: Expected ${expected.timestamp.seconds} (${Timestamps.toString(expected.timestamp)}), got ${actual.timestamp.seconds} (${Timestamps.toString(actual.timestamp)})"
            }
        } else {
            // If not checking timestamp exactly, maybe log it
             println("$testName: Timestamp for ${actual.currencyPair}: ${Timestamps.toString(actual.timestamp)}")
        }
    }
}

// Separate serializable checker for default-only case
class DefaultsOnlyChecker(private val expectedKeys: List<String>) : SerializableFunction<Iterable<KV<String, Candle>>, Void?>, Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    override fun apply(output: Iterable<KV<String, Candle>>): Void? {
        val candles = output.toList()
        val actualKeys = candles.map { it.key }.toSet()
        assert(candles.size == expectedKeys.size) { "DefaultsOnly: Expected ${expectedKeys.size} default candles, found ${candles.size}" }
        assert(actualKeys == expectedKeys.toSet()) { "DefaultsOnly: Key mismatch. Expected ${expectedKeys.toSet()}, got ${actualKeys}"}
        // Optionally check if they are indeed default candles (e.g., volume is 0)
        candles.forEach {
            assert(it.value.volume == 0.0) { "DefaultsOnly: Expected 0 volume for default candle ${it.key}, got ${it.value.volume}"}
        }
        return null
    }
}


class TradeToCandleTest : Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    // Allows inspection of pipeline structure, use TestPipeline.create() for execution checks
    @Rule
    @JvmField
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // Guice injection target for the factory
    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    // Guice injection target for the dependency (will be injected into TradeToCandle)
    @Inject
    lateinit var candleCreatorFn: CandleCreatorFn

    // Define test currency pairs
    private val btcUsd = CurrencyPair.fromSymbol("BTC/USD")
    private val ethUsd = CurrencyPair.fromSymbol("ETH/USD")

    // Define the list of pairs the transform should expect
    private val currencyPairsInstance = ImmutableList.of(btcUsd, ethUsd)
    private val defaultTestPrice = 0.0 // Price for default candles

    // Bind the supplier for Guice testing
    @Bind
    private val currencyPairSupplier: Supplier<List<CurrencyPair>> =
        Suppliers.ofInstance(currencyPairsInstance)


    // Corrected expected default candle timestamps (representing window end second)
    // Window [10:00:00, 10:01:00) -> maxTimestamp is 10:00:59.999 -> second is 10:00:59
    private val oneMinWindowEndTs = Timestamps.fromSeconds(Instant.parse("2023-01-01T10:00:59Z").epochSecond)
    // Window [10:00:00, 10:05:00) -> maxTimestamp is 10:04:59.999 -> second is 10:04:59
    private val fiveMinWindowEndTs = Timestamps.fromSeconds(Instant.parse("2023-01-01T10:04:59Z").epochSecond)


    @Before
    fun setUp() {
        // Configure Guice for testing
        val testModule = BoundFieldModule.of(this) // Binds fields annotated with @Bind
        val modules: List<Module> = listOf(
            testModule,
            // Explicitly provide bindings needed by the classes under test
            object : AbstractModule() { // Use AbstractModule
                override fun configure() {
                    // Bind CandleCreatorFn directly as it has an @Inject constructor
                    // No need to bind if it's just injected into TradeToCandle which is created by factory
                     bind(CandleCreatorFn::class.java) // Ensure Guice knows about it
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

    @Test
    fun testTradeToCandlesOneMinuteWindow() {
        val windowDuration = Duration.standardMinutes(1)
        // Trades within the [10:00:00, 10:01:00) window
        val t1 = Instant.parse("2023-01-01T10:00:15Z") // First trade
        val t2 = Instant.parse("2023-01-01T10:00:45Z") // Last trade

        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, t1), // Open=50k, Low=50k
            createTrade("BTC/USD", 50100.0, 0.5, t2)  // High=50.1k, Close=50.1k, Vol=1.5
        )

        // Expected actual candle for BTC/USD
        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
             // Timestamp based on the *first* trade in CandleCreatorFn logic
            .setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()

        // Expected default candle for ETH/USD (no trades)
        val expectedDefaultEthCandle = Candle.newBuilder()
            .setCurrencyPair("ETH/USD")
            .setOpen(defaultTestPrice)
            .setHigh(defaultTestPrice)
            .setLow(defaultTestPrice)
            .setClose(defaultTestPrice)
            .setVolume(0.0)
            // Timestamp should be the window end (maxTimestamp)
            .setTimestamp(oneMinWindowEndTs)
            .build()

        val result = runTransform(trades, windowDuration)

        // Use the checker to assert results
        PAssert.that(result)
            .satisfies(CandleChecker(expectedBtcCandle, expectedDefaultEthCandle, "testTradeToCandlesOneMinuteWindow"))

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testTradeToCandlesFiveMinuteWindow() {
        val windowDuration = Duration.standardMinutes(5)
         // Trades within the [10:00:00, 10:05:00) window
        val t1 = Instant.parse("2023-01-01T10:01:30Z") // First trade
        val t2 = Instant.parse("2023-01-01T10:04:45Z") // Last trade

        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, t1), // Open=50k, Low=50k
             createTrade("BTC/USD", 49900.0, 0.2, Instant.parse("2023-01-01T10:02:00Z")), // Lower Low=49.9k
            createTrade("BTC/USD", 50100.0, 0.5, t2)  // High=50.1k, Close=50.1k, Vol=1.7
        )

        // Expected actual candle for BTC/USD
        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(49900.0)
            .setClose(50100.0)
            .setVolume(1.7)
            // Timestamp based on the *first* trade
            .setTimestamp(Timestamps.fromMillis(t1.millis))
            .build()

        // Expected default candle for ETH/USD
        val expectedDefaultEthCandle = Candle.newBuilder()
            .setCurrencyPair("ETH/USD")
            .setOpen(defaultTestPrice)
            .setHigh(defaultTestPrice)
            .setLow(defaultTestPrice)
            .setClose(defaultTestPrice)
            .setVolume(0.0)
            // Timestamp should be the window end (maxTimestamp) - Corrected
            .setTimestamp(fiveMinWindowEndTs)
            .build()

        val result = runTransform(trades, windowDuration)

        PAssert.that(result)
             .satisfies(CandleChecker(expectedBtcCandle, expectedDefaultEthCandle, "testTradeToCandlesFiveMinuteWindow"))


        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testTradeToCandles_defaultsOnly() {
        val windowDuration = Duration.standardMinutes(1)
        val trades = emptyList<Trade>() // No input trades

        val result = runTransform(trades, windowDuration)

        // Expecting default candles for BOTH BTC/USD and ETH/USD
        // Use a simpler assertion focusing on keys and count for the empty case
        PAssert.that(result).satisfies(DefaultsOnlyChecker(listOf("BTC/USD", "ETH/USD")))

        pipeline.run().waitUntilFinish()
    }

    // Helper to run the transform
    private fun runTransform(
        trades: List<Trade>,
        windowDuration: Duration
    ): PCollection<KV<String, Candle>> {
        // Create the transform instance using the factory
        val transform = tradeToCandleFactory.create(windowDuration, defaultTestPrice)
        val tradeCoder: Coder<Trade> = ProtoCoder.of(Trade::class.java)

        // Create input PCollection
        val input: PCollection<Trade>
        if (trades.isEmpty()) {
            // Create empty PCollection with coder and default windowing (Global)
            // The transform applies its own windowing later.
            input = pipeline.apply("CreateEmptyTrades", Create.empty<Trade>(tradeCoder))
        } else {
            // Create timestamped PCollection for testing windowing
            val timestampedTrades = trades.map { trade ->
                val instant = Instant(Timestamps.toMillis(trade.timestamp))
                TimestampedValue.of(trade, instant)
            }
            input = pipeline.apply("CreateTestTrades", Create.timestamped<Trade>(timestampedTrades).withCoder(tradeCoder))
        }

        // Apply the transform
        return input.apply("TradeToCandles", transform)
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
            .setExchange("TEST") // Use a non-"DEFAULT" exchange name
            .setTradeId("test-${System.nanoTime()}")
            .setTimestamp(Timestamps.fromMillis(timestamp.millis))
            .build()
    }
}
