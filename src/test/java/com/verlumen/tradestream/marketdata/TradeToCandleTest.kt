package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.TypeLiteral
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.protobuf.Timestamp
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

class TradeToCandleTest {

    @Rule
    @JvmField
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    private val currencyPairs = ImmutableList.of(
        CurrencyPair.fromSymbol("BTC/USD"),
        CurrencyPair.fromSymbol("ETH/USD")
    )

    @Before
    fun setUp() {
        // Setup test injection with BoundFieldModule
        val testModule = BoundFieldModule.of(this)

        // Add our market data module and any test-specific bindings
        val modules: List<Module> = listOf(
            testModule,
            // Use Kotlin ::class.java syntax instead of Java .class
            FactoryModuleBuilder()
                .implement(CandleCreatorFn::class.java, CandleCreatorFn::class.java)
                .build(CandleCreatorFn.Factory::class.java),
            // Use Kotlin ::class.java syntax instead of Java .class
            FactoryModuleBuilder()
                .implement(TradeToCandle::class.java, TradeToCandle::class.java)
                .build(TradeToCandle.Factory::class.java),
            object : AbstractModule() {
                override fun configure() {
                    // Bind currency pairs supplier for tests
                    bind(object : TypeLiteral<Supplier<List<CurrencyPair>>>() {})
                        .toInstance(Supplier { currencyPairs })
                }
            }
        )

        // Create the injector and inject fields
        val injector = Guice.createInjector(modules)
        injector.injectMembers(this)
    }

    @Test
    fun testTradeToCandlesOneMinute() {
        // Create test data - two trades for BTC/USD in same minute
        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, Instant.parse("2023-01-01T10:00:30Z")),
            createTrade("BTC/USD", 50100.0, 0.5, Instant.parse("2023-01-01T10:00:45Z"))
        )

        // Define expected output - one candle with combined data
        val expectedCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamp.newBuilder().setSeconds(Instant.parse("2023-01-01T10:00:30Z").millis / 1000))
            .build()

        // Run the transform
        val result = runTransform(trades, Duration.standardMinutes(1))

        // Verify expectations
        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList()

                    // Should have candles for both currency pairs
                    assert(candles.size == 2) { "Expected 2 candles, found ${candles.size}" }

                    // Find BTC/USD candle
                    val btcCandle = candles.find { it.key == "BTC/USD" }?.value
                    assert(btcCandle != null) { "Missing BTC/USD candle" }

                    // Verify candle values match expectations
                    assertCandle(expectedCandle, btcCandle!!)

                    // ETH/USD should have a default candle
                    val ethCandle = candles.find { it.key == "ETH/USD" }?.value
                    assert(ethCandle != null) { "Missing ETH/USD default candle" }
                    assert(ethCandle!!.open == 0.0) { "Expected default price 0.0, got ${ethCandle.open}" }
                    assert(ethCandle.volume == 0.0) { "Expected zero volume, got ${ethCandle.volume}" }

                    return null
                }
            })

        pipeline.run()
    }

    @Test
    fun testTradeToCandlesFiveMinute() {
        // Create test data - trades in different minutes but same 5-min window
        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, Instant.parse("2023-01-01T10:00:30Z")),
            createTrade("BTC/USD", 50100.0, 0.5, Instant.parse("2023-01-01T10:04:45Z"))
        )

        // Run the transform with 5-minute window
        val result = runTransform(trades, Duration.standardMinutes(5))

        // Verify expectations
        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList()

                    // Should have a single combined 5-minute candle for BTC/USD
                    val btcCandle = candles.find { it.key == "BTC/USD" }?.value
                    assert(btcCandle != null) { "Missing BTC/USD candle" }

                    // Verify it's a combined candle
                    assert(btcCandle!!.high == 50100.0) { "Expected high of 50100.0, got ${btcCandle.high}" }
                    assert(btcCandle.volume == 1.5) { "Expected combined volume of 1.5, got ${btcCandle.volume}" }

                    return null
                }
            })

        pipeline.run()
    }

    @Test
    fun testTradeToCandles_defaultsOnly() {
        // No trades, should produce default candles for all currency pairs
        val trades = listOf<Trade>()

        // Run the transform
        val result = runTransform(trades, Duration.standardMinutes(1))

        // Verify expectations
        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList()

                    // Should have default candles for both pairs
                    assert(candles.size == 2) { "Expected 2 default candles, found ${candles.size}" }

                    // Verify default values
                    for (kv in candles) {
                        assert(kv.value.volume == 0.0) { "Expected zero volume for default candle" }
                        assert(kv.value.open == 0.0) { "Expected default price 0.0" }
                    }

                    return null
                }
            })

        pipeline.run()
    }

    private fun runTransform(
        trades: List<Trade>,
        windowDuration: Duration
    ): PCollection<KV<String, Candle>> {
        // Create our transform using the injected factory
        val transform = tradeToCandleFactory.create(windowDuration, 0.0)

        // Apply the transform to our test data
        val input = pipeline.apply("CreateTestTrades", Create.of(trades))
        return input.apply("TradeToCandles", transform)
    }

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
            .setTradeId("test-${System.nanoTime()}")
            .setTimestamp(Timestamp.newBuilder().setSeconds(timestamp.millis / 1000))
            .build()
    }

    private fun assertCandle(expected: Candle, actual: Candle) {
        assert(expected.currencyPair == actual.currencyPair) {
            "Currency pair mismatch: ${expected.currencyPair} vs ${actual.currencyPair}"
        }
        assert(expected.open == actual.open) { "Open price mismatch: ${expected.open} vs ${actual.open}" }
        assert(expected.high == actual.high) { "High price mismatch: ${expected.high} vs ${actual.high}" }
        assert(expected.low == actual.low) { "Low price mismatch: ${expected.low} vs ${actual.low}" }
        assert(expected.close == actual.close) { "Close price mismatch: ${expected.close} vs ${actual.close}" }
        assert(expected.volume == actual.volume) { "Volume mismatch: ${expected.volume} vs ${actual.volume}" }
    }
}
