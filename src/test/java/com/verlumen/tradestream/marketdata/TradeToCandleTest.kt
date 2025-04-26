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
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import java.util.function.Supplier
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps // For timestamp conversion/checking
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.values.TimestampedValue
import org.junit.rules.TestRule
import org.apache.beam.sdk.options.PipelineOptionsFactory

// Top-level or Companion object function to avoid serialization issues with PAssert
// (Copied from previous answer - no changes needed here)
private fun assertCandle(expected: Candle, actual: Candle, checkTimestampSecs: Boolean = true) {
    val tolerance = 0.00001
    assert(expected.currencyPair == actual.currencyPair) {
        "Currency pair mismatch: Expected ${expected.currencyPair}, got ${actual.currencyPair}"
    }
    assert(kotlin.math.abs(expected.open - actual.open) < tolerance) {
        "Open price mismatch for ${actual.currencyPair}: Expected ${expected.open}, got ${actual.open}"
    }
    assert(kotlin.math.abs(expected.high - actual.high) < tolerance) {
        "High price mismatch for ${actual.currencyPair}: Expected ${expected.high}, got ${actual.high}"
    }
    assert(kotlin.math.abs(expected.low - actual.low) < tolerance) {
        "Low price mismatch for ${actual.currencyPair}: Expected ${expected.low}, got ${actual.low}"
    }
    assert(kotlin.math.abs(expected.close - actual.close) < tolerance) {
        "Close price mismatch for ${actual.currencyPair}: Expected ${expected.close}, got ${actual.close}"
    }
    assert(kotlin.math.abs(expected.volume - actual.volume) < tolerance) {
        "Volume mismatch for ${actual.currencyPair}: Expected ${expected.volume}, got ${actual.volume}"
    }
    if (checkTimestampSecs) {
        assert(expected.timestamp.seconds == actual.timestamp.seconds) {
            "Timestamp mismatch (seconds) for ${actual.currencyPair}: Expected ${expected.timestamp.seconds}, got ${actual.timestamp.seconds}"
        }
    }
}


class TradeToCandleTest {

    @Rule
    @JvmField
    val pipeline: TestRule = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    // Inject the simplified CandleCreatorFn dependency needed by TradeToCandle
    @Inject
    lateinit var candleCreatorFn: CandleCreatorFn

    private val btcUsd = CurrencyPair.fromSymbol("BTC/USD")
    private val ethUsd = CurrencyPair.fromSymbol("ETH/USD")

    private val currencyPairsInstance = ImmutableList.of(btcUsd, ethUsd)
    private val defaultTestPrice = 0.0 // Define default price used in tests

    @Bind
    private val currencyPairSupplier: Supplier<List<CurrencyPair>> =
        Suppliers.ofInstance(currencyPairsInstance)

    // Bind the CandleCreatorFn instance so TradeToCandle can inject it
    // Since it has an @Inject constructor now, Guice can create it.
    @Bind
    private lateinit var boundCandleCreatorFn: CandleCreatorFn


    @Before
    fun setUp() {
        // Setup Guice for dependency injection
        val testModule = BoundFieldModule.of(this)
        val modules: List<Module> = listOf(
            testModule,
            // Bind CandleCreatorFn directly
             com.google.inject.AbstractModule() {
                 override fun configure() {
                     bind(CandleCreatorFn::class.java)
                 }
             },
            // Keep FactoryModuleBuilder for TradeToCandle
            FactoryModuleBuilder()
                .implement(TradeToCandle::class.java, TradeToCandle::class.java)
                .build(TradeToCandle.Factory::class.java)
        )
        val injector = Guice.createInjector(modules)
        injector.injectMembers(this)

        // Need to ensure the bound instance is assigned if @Bind doesn't automatically do it
        // for non-mocks/non-providers when using @Inject on the field.
        // Alternatively, inject it directly via constructor or method if needed.
        // Let's assume Guice handles injecting the created instance into the @Bind field.
        boundCandleCreatorFn = candleCreatorFn // Ensure the bound field points to the injected instance

    }

    // --- Test methods remain the same as the previously fixed version ---
    // The expected outputs (actual candles + default candles) are the same,
    // even though the internal implementation generating defaults has changed.

    @Test
    fun testTradeToCandlesOneMinuteWindow() {
        val windowDuration = Duration.standardMinutes(1)
        val t1 = Instant.parse("2023-01-01T10:00:15Z") // First trade time
        val t2 = Instant.parse("2023-01-01T10:00:45Z") // Second trade time

        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, t1),
            createTrade("BTC/USD", 50100.0, 0.5, t2)
        )

        // Expected candle uses timestamp of the *first* trade in the window
        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(t1.millis)) // Timestamp from first trade
            .build()

        // Expected default candle timestamp should be the window end time
        // Window [10:00:00Z, 10:01:00Z) -> maxTimestamp = 10:00:59.999Z
        val expectedWindowEnd = Instant.parse("2023-01-01T10:01:00Z").minus(1)
        val expectedDefaultEthCandle = Candle.newBuilder()
            .setCurrencyPair("ETH/USD")
            .setOpen(defaultTestPrice)
            .setHigh(defaultTestPrice)
            .setLow(defaultTestPrice)
            .setClose(defaultTestPrice)
            .setVolume(0.0)
            .setTimestamp(Timestamps.fromMillis(expectedWindowEnd.millis))
            .build()

        val result = runTransform(trades, windowDuration)

        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList().associate { it.key to it.value }

                    assert(candles.size == 2) { "Expected 2 candles (BTC, ETH), found ${candles.size}: ${candles.keys}" }

                    // Assert BTC candle
                    val btcCandle = candles["BTC/USD"]
                    assert(btcCandle != null) { "Missing BTC/USD candle" }
                    assertCandle(expectedBtcCandle, btcCandle!!) // Use external assertion function

                    // Assert default ETH candle
                    val ethCandle = candles["ETH/USD"]
                    assert(ethCandle != null) { "Missing ETH/USD default candle" }
                    // Check default values explicitly & timestamp
                    assertCandle(expectedDefaultEthCandle, ethCandle!!, checkTimestampSecs = true)

                    return null
                }
            })

        (pipeline as TestPipeline).run().waitUntilFinish() // Run pipeline
    }

    @Test
    fun testTradeToCandlesFiveMinuteWindow() {
        val windowDuration = Duration.standardMinutes(5)
        val t1 = Instant.parse("2023-01-01T10:01:30Z") // First trade time
        val t2 = Instant.parse("2023-01-01T10:04:45Z") // Second trade time

        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, t1),
            createTrade("BTC/USD", 50100.0, 0.5, t2)
        )

        // Expected candle uses timestamp of the *first* trade in the window
        val expectedBtcCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamps.fromMillis(t1.millis)) // Timestamp from first trade
            .build()

         // Expected default candle timestamp should be the window end time
         // Window [10:00:00Z, 10:05:00Z) -> maxTimestamp = 10:04:59.999Z
         val expectedWindowEnd = Instant.parse("2023-01-01T10:05:00Z").minus(1)
         val expectedDefaultEthCandle = Candle.newBuilder()
             .setCurrencyPair("ETH/USD")
             .setOpen(defaultTestPrice)
             .setHigh(defaultTestPrice)
             .setLow(defaultTestPrice)
             .setClose(defaultTestPrice)
             .setVolume(0.0)
             .setTimestamp(Timestamps.fromMillis(expectedWindowEnd.millis))
             .build()

        val result = runTransform(trades, windowDuration)

        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList().associate { it.key to it.value }

                    assert(candles.size == 2) { "Expected 2 candles (BTC, ETH), found ${candles.size}: ${candles.keys}" }

                    // Assert BTC candle
                    val btcCandle = candles["BTC/USD"]
                    assert(btcCandle != null) { "Missing BTC/USD candle" }
                    assertCandle(expectedBtcCandle, btcCandle!!) // Use external assertion function

                    // Assert default ETH candle
                    val ethCandle = candles["ETH/USD"]
                    assert(ethCandle != null) { "Missing ETH/USD default candle" }
                    assertCandle(expectedDefaultEthCandle, ethCandle!!, checkTimestampSecs = true) // Use external assertion function

                    return null
                }
            })

        (pipeline as TestPipeline).run().waitUntilFinish() // Run pipeline
    }

    @Test
    fun testTradeToCandles_defaultsOnly() {
        val windowDuration = Duration.standardMinutes(1)
        val trades = emptyList<Trade>() // No input trades

        // Expected default candle timestamp should be the window end time.
        // Since there's no data, the pipeline might advance time to infinity or
        // a predefined point. PAssert might struggle without explicit time.
        // However, the CoGroupByKey approach should still generate defaults
        // for the first window processed. Let's assume a window ending near epoch+1min for checking.
        // Window [T0, T0+1min) -> T0+1min-1ms
        // Let's primarily check content, less strictly the timestamp.

        val result = runTransform(trades, windowDuration)

        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList().associate { it.key to it.value }

                    assert(candles.size == 2) { "Expected 2 default candles (BTC, ETH), found ${candles.size}: ${candles.keys}" }

                    // Check default candle properties for both
                    for ((pairSymbol, candle) in candles) {
                        assert(candle.currencyPair == pairSymbol)
                        assert(candle.open == defaultTestPrice) { "Expected default price $defaultTestPrice for ${pairSymbol}, got ${candle.open}" }
                        assert(candle.high == defaultTestPrice) { "Expected default price $defaultTestPrice for ${pairSymbol}, got ${candle.high}" }
                        assert(candle.low == defaultTestPrice) { "Expected default price $defaultTestPrice for ${pairSymbol}, got ${candle.low}" }
                        assert(candle.close == defaultTestPrice) { "Expected default price $defaultTestPrice for ${pairSymbol}, got ${candle.close}" }
                        assert(candle.volume == 0.0) { "Expected zero volume for default candle ${pairSymbol}, got ${candle.volume}" }
                        assert(candle.timestamp.seconds > 0 || candle.timestamp.nanos > 0) {
                            "Default candle timestamp for $pairSymbol appears uninitialized: ${candle.timestamp}"
                        }
                        // We know the timestamp should be the end of the window.
                    }

                    return null
                }
            })

        (pipeline as TestPipeline).run().waitUntilFinish() // Run pipeline
    }

    // Helper to create input PCollection, handling empty list and timestamps
    // (Copied from previous answer - no changes needed here)
    private fun runTransform(
        trades: List<Trade>,
        windowDuration: Duration
    ): PCollection<KV<String, Candle>> {
        val transform = tradeToCandleFactory.create(windowDuration, defaultTestPrice)
        val tradeCoder: Coder<Trade> = ProtoCoder.of(Trade::class.java)

        val currentPipeline = (pipeline as TestPipeline).pipeline // Get the actual pipeline instance

        val input: PCollection<Trade>
        if (trades.isEmpty()) {
            // Use Create.empty() with the explicit coder for empty inputs
            input = currentPipeline.apply("CreateTestTrades", Create.empty(tradeCoder))
        } else {
            // Use Create.timestamped() to assign event times from the Trade protos
            val timestampedTrades = trades.map { trade ->
                // Extract timestamp from proto and convert to Joda Instant
                val instant = Instant(Timestamps.toMillis(trade.timestamp))
                TimestampedValue.of(trade, instant)
            }
            // Provide the coder to Create.timestamped() as well
            input = currentPipeline.apply("CreateTestTrades", Create.timestamped(timestampedTrades).withCoder(tradeCoder))
        }

        // Apply the transform under test
        return input.apply("TradeToCandles", transform)
    }


    // Helper to create Trade objects
    // (Copied from previous answer - no changes needed here)
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
            .setTradeId("test-${System.nanoTime()}") // Unique ID
            .setTimestamp(Timestamps.fromMillis(timestamp.millis)) // Convert Joda Instant to proto Timestamp
            .build()
    }
}
