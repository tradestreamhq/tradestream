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

class TradeToCandleTest {

    @Rule
    @JvmField
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @Inject
    lateinit var tradeToCandleFactory: TradeToCandle.Factory

    private val currencyPairsInstance = ImmutableList.of(
        CurrencyPair.fromSymbol("BTC/USD"),
        CurrencyPair.fromSymbol("ETH/USD")
    )

    @Bind
    private val currencyPairSupplier: Supplier<List<CurrencyPair>> =
        Suppliers.ofInstance(currencyPairsInstance)

    @Before
    fun setUp() {
        val testModule = BoundFieldModule.of(this)

        val modules: List<Module> = listOf(
            testModule,
            FactoryModuleBuilder()
                .implement(CandleCreatorFn::class.java, CandleCreatorFn::class.java)
                .build(CandleCreatorFn.Factory::class.java),
            FactoryModuleBuilder()
                .implement(TradeToCandle::class.java, TradeToCandle::class.java)
                .build(TradeToCandle.Factory::class.java)
        )

        val injector = Guice.createInjector(modules)
        injector.injectMembers(this)
    }

    @Test
    fun testTradeToCandlesOneMinute() {
        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, Instant.parse("2023-01-01T10:00:30Z")),
            createTrade("BTC/USD", 50100.0, 0.5, Instant.parse("2023-01-01T10:00:45Z"))
        )

        val expectedCandle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setOpen(50000.0)
            .setHigh(50100.0)
            .setLow(50000.0)
            .setClose(50100.0)
            .setVolume(1.5)
            .setTimestamp(Timestamp.newBuilder().setSeconds(Instant.parse("2023-01-01T10:00:30Z").millis / 1000))
            .build()

        val result = runTransform(trades, Duration.standardMinutes(1))

        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList()

                    assert(candles.size == 2) { "Expected 2 candles, found ${candles.size}" }

                    val btcCandle = candles.find { it.key == "BTC/USD" }?.value
                    assert(btcCandle != null) { "Missing BTC/USD candle" }
                    assertCandle(expectedCandle, btcCandle!!)

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
        val trades = listOf(
            createTrade("BTC/USD", 50000.0, 1.0, Instant.parse("2023-01-01T10:00:30Z")),
            createTrade("BTC/USD", 50100.0, 0.5, Instant.parse("2023-01-01T10:04:45Z"))
        )

        val result = runTransform(trades, Duration.standardMinutes(5))

        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList()

                    assert(candles.size == 2) // Expecting BTC and default ETH

                    val btcCandle = candles.find { it.key == "BTC/USD" }?.value
                    assert(btcCandle != null) { "Missing BTC/USD candle" }

                    // Verify combined candle properties
                    assert(btcCandle!!.open == 50000.0) { "Expected open of 50000.0, got ${btcCandle.open}" }
                    assert(btcCandle.high == 50100.0) { "Expected high of 50100.0, got ${btcCandle.high}" }
                    assert(btcCandle.low == 50000.0) { "Expected low of 50000.0, got ${btcCandle.low}" }
                    assert(btcCandle.close == 50100.0) { "Expected close of 50100.0, got ${btcCandle.close}" }
                    assert(btcCandle.volume == 1.5) { "Expected combined volume of 1.5, got ${btcCandle.volume}" }

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
    fun testTradeToCandles_defaultsOnly() {
        val trades = emptyList<Trade>()

        val result = runTransform(trades, Duration.standardMinutes(1))

        PAssert.that(result)
            .satisfies(object : SerializableFunction<Iterable<KV<String, Candle>>, Void?> {
                override fun apply(output: Iterable<KV<String, Candle>>): Void? {
                    val candles = output.toList()

                    assert(candles.size == 2) { "Expected 2 default candles, found ${candles.size}" }

                    for (kv in candles) {
                        assert(kv.value.volume == 0.0) { "Expected zero volume for default candle ${kv.key}" }
                        assert(kv.value.open == 0.0) { "Expected default price 0.0 for ${kv.key}" }
                        assert(kv.value.high == 0.0) { "Expected default price 0.0 for ${kv.key}" }
                        assert(kv.value.low == 0.0) { "Expected default price 0.0 for ${kv.key}" }
                        assert(kv.value.close == 0.0) { "Expected default price 0.0 for ${kv.key}" }
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
        val transform = tradeToCandleFactory.create(windowDuration, 0.0) // Using 0.0 as default price
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
        val tolerance = 0.00001
        assert(kotlin.math.abs(expected.open - actual.open) < tolerance) { "Open price mismatch: ${expected.open} vs ${actual.open}" }
        assert(kotlin.math.abs(expected.high - actual.high) < tolerance) { "High price mismatch: ${expected.high} vs ${actual.high}" }
        assert(kotlin.math.abs(expected.low - actual.low) < tolerance) { "Low price mismatch: ${expected.low} vs ${actual.low}" }
        assert(kotlin.math.abs(expected.close - actual.close) < tolerance) { "Close price mismatch: ${expected.close} vs ${actual.close}" }
        assert(kotlin.math.abs(expected.volume - actual.volume) < tolerance) { "Volume mismatch: ${expected.volume} vs ${actual.volume}" }
        // Note: Timestamp comparison might need adjustment based on exact windowing behavior expectations
        assert(expected.timestamp.seconds == actual.timestamp.seconds) { "Timestamp mismatch: ${expected.timestamp.seconds} vs ${actual.timestamp.seconds}" }
    }
}
