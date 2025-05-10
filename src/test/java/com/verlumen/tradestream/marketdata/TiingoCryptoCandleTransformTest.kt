package com.verlumen.tradestream.marketdata

import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.BoundFieldModule
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.coders.CoderRegistry
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.Mockito.`when`
import org.mockito.MockitoAnnotations
import java.io.Serializable
import java.util.function.Supplier
import com.verlumen.tradestream.instruments.CurrencyPair

/**
 * Abstract DoFn representing the fetcher. The SUT uses a factory to create instances of this.
 */
abstract class TiingoCryptoFetcherFn(
    @Suppress("UNUSED_PARAMETER") @com.google.inject.assistedinject.Assisted protected val granularity: Duration,
    @Suppress("UNUSED_PARAMETER") @com.google.inject.assistedinject.Assisted protected val apiKey: String
) : DoFn<KV<String, Void?>, KV<String, Candle>>(), Serializable {

    interface Factory {
        fun create(granularity: Duration, apiKey: String): TiingoCryptoFetcherFn
    }

    companion object {
        private const val serialVersionUID = 1L
    }
}

// --- Test Implementations of Fetcher ---

/**
 * A test implementation of TiingoCryptoFetcherFn that emits a predefined set of candles.
 * This version is stateless and will emit candles every time it's triggered for a symbol.
 */
class StatelessTestTiingoCryptoFetcherFnImpl(
    granularity: Duration,
    apiKey: String,
    private val candlesToEmitPerSymbol: Map<String, List<Candle>>
) : TiingoCryptoFetcherFn(granularity, apiKey) {

    @ProcessElement
    fun process(context: ProcessContext) {
        val inputKv = context.element() as KV<String, Void?>
        val symbol = inputKv.key
        candlesToEmitPerSymbol[symbol]?.forEach { candle ->
            if (candle.currencyPair == symbol) { // Ensure candle matches the symbol
                context.output(KV.of(symbol, candle))
            }
        }
    }
    companion object { private const val serialVersionUID = 1L }
}

/**
 * A stateful test implementation of TiingoCryptoFetcherFn that emits candles only once per symbol.
 * Useful for testing scenarios with PeriodicImpulse where multiple triggers might occur.
 */
class StatefulTestTiingoCryptoFetcherFnImpl(
    granularity: Duration,
    apiKey: String,
    private val candlesToEmitPerSymbol: Map<String, List<Candle>>
) : TiingoCryptoFetcherFn(granularity, apiKey) {

    // N.B. State in DoFns should be handled carefully (e.g. Beam State API for fault tolerance).
    // For this test DoFn, simple mutable state is acceptable as TestPipeline runs locally.
    @Transient // Beam might try to serialize this; mark transient if not part of Beam state
    private val emittedSymbols = mutableSetOf<String>()

    @ProcessElement
    fun process(context: ProcessContext) {
        val inputKv = context.element() as KV<String, Void?>
        val symbol = inputKv.key
        synchronized(emittedSymbols) { // Synchronize access if multiple threads could process elements for the same DoFn instance
            if (!emittedSymbols.contains(symbol)) {
                candlesToEmitPerSymbol[symbol]?.forEach { candle ->
                    if (candle.currencyPair == symbol) {
                        context.output(KV.of(symbol, candle))
                    }
                }
                emittedSymbols.add(symbol)
            }
        }
    }
    companion object { private const val serialVersionUID = 1L }
}


@RunWith(JUnit4::class)
class TiingoCryptoCandleTransformTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @Mock
    private lateinit var mockCurrencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>

    @Mock
    private lateinit var mockTiingoFetcherFnFactory: TiingoCryptoFetcherFn.Factory

    @Inject
    private lateinit var transformFactory: TiingoCryptoCandleTransform.Factory // Factory for the class under test

    private lateinit var underTest: TiingoCryptoCandleTransform

    private val granularity = Duration.standardMinutes(1)
    private val apiKey = "testApiKey"

    // Test data
    private val btcUsd = CurrencyPair.fromSymbol("BTC/USD")
    private val ethUsd = CurrencyPair.fromSymbol("ETH/USD")
    private val currencyPairsList = listOf(btcUsd, ethUsd)

    private val now = Instant.now()
    private val candleBtc1 = Candle.newBuilder().setOpen(10000.0).setHigh(10100.0).setLow(9900.0).setClose(10050.0).setVolume(100.0).setTimestamp(com.google.protobuf.util.Timestamps.fromMillis(now.millis)).setCurrencyPair(btcUsd.symbol()).build()
    private val candleEth1 = Candle.newBuilder().setOpen(300.0).setHigh(305.0).setLow(295.0).setClose(302.0).setVolume(500.0).setTimestamp(com.google.protobuf.util.Timestamps.fromMillis(now.millis)).setCurrencyPair(ethUsd.symbol()).build()

    private val candlesToEmitMap: Map<String, List<Candle>> = mapOf(
        btcUsd.symbol() to listOf(candleBtc1),
        ethUsd.symbol() to listOf(candleEth1)
    )

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Create a custom module that explicitly binds our mocks
        val testModule = object : AbstractModule() {
            override fun configure() {
                // Explicitly bind the mocked dependencies
                bind(object : com.google.inject.TypeLiteral<Supplier<List<CurrencyPair>>>() {})
                    .toInstance(mockCurrencyPairSupplier)
                
                bind(TiingoCryptoFetcherFn.Factory::class.java)
                    .toInstance(mockTiingoFetcherFnFactory)
                
                // Install the factory module for TiingoCryptoCandleTransform
                install(
                    FactoryModuleBuilder()
                        .implement(TiingoCryptoCandleTransform::class.java, TiingoCryptoCandleTransform::class.java)
                        .build(TiingoCryptoCandleTransform.Factory::class.java)
                )
            }
        }

        // Create the injector with our custom module
        Guice.createInjector(
            BoundFieldModule.of(this), // For general field binding
            testModule // Our custom module with explicit bindings
        ).injectMembers(this) // Injects transformFactory

        // Common mock setups
        `when`(mockCurrencyPairSupplier.get()).thenReturn(currencyPairsList)

        // Create the instance under test using its Guice-provided factory.
        // The fetcherFnFactory used by `underTest` will be the mocked one.
        underTest = transformFactory.create(granularity, apiKey)

        // Register coders if necessary, especially for Kotlin data classes
        val coderRegistry: CoderRegistry = pipeline.coderRegistry
        
        // Explicit registration for necessary classes
        try { coderRegistry.getCoder(CurrencyPair::class.java) }
        catch (e: Exception) { coderRegistry.registerCoderForClass(CurrencyPair::class.java, SerializableCoder.of(CurrencyPair::class.java)) }
        try { coderRegistry.getCoder(Candle::class.java) }
        catch (e: Exception) { coderRegistry.registerCoderForClass(Candle::class.java, SerializableCoder.of(Candle::class.java)) }
    }

    @Test
    fun `expand with PCollection input should fetch candles for each currency pair`() {
        // Arrange
        val testInstant = Instant.now()
        val impulse: PCollection<Instant> = pipeline.apply("CreateImpulse", Create.of(testInstant))

        // Configure the mock fetcher factory to return a stateless test fetcher
        val statelessTestFetcher = StatelessTestTiingoCryptoFetcherFnImpl(granularity, apiKey, candlesToEmitMap)
        `when`(mockTiingoFetcherFnFactory.create(granularity, apiKey)).thenReturn(statelessTestFetcher)

        val expectedOutput: List<KV<String, Candle>> = listOf(
            KV.of(btcUsd.symbol(), candleBtc1),
            KV.of(ethUsd.symbol(), candleEth1)
        )

        // Act
        val result: PCollection<KV<String, Candle>> = underTest.expand(impulse)

        // Assert
        PAssert.that(result).containsInAnyOrder(expectedOutput)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `expand with Pipeline input should setup PeriodicImpulse and fetch candles once per pair`() {
        // Arrange
        // Configure the mock fetcher factory to return a stateful test fetcher
        // This ensures that even if PeriodicImpulse fires multiple times, we only get one set of candles.
        val statefulTestFetcher = StatefulTestTiingoCryptoFetcherFnImpl(granularity, apiKey, candlesToEmitMap)
        `when`(mockTiingoFetcherFnFactory.create(granularity, apiKey)).thenReturn(statefulTestFetcher)

        val expectedOutput: List<KV<String, Candle>> = listOf(
            KV.of(btcUsd.symbol(), candleBtc1),
            KV.of(ethUsd.symbol(), candleEth1)
        )

        // Act
        val result: PCollection<KV<String, Candle>> = underTest.expand(pipeline) // pipeline is the TestPipeline rule

        // Assert
        PAssert.that(result).containsInAnyOrder(expectedOutput)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `expand with PCollection input and empty currency pairs list should produce empty PCollection`() {
        // Arrange
        `when`(mockCurrencyPairSupplier.get()).thenReturn(emptyList())

        // The fetcher function won't be called if there are no pairs,
        // but for completeness, ensure the factory mock is in place.
        val statelessTestFetcher = StatelessTestTiingoCryptoFetcherFnImpl(granularity, apiKey, emptyMap())
        `when`(mockTiingoFetcherFnFactory.create(granularity, apiKey)).thenReturn(statelessTestFetcher)

        val testInstant = Instant.now()
        val impulse: PCollection<Instant> = pipeline.apply("CreateEmptyImpulse", Create.of(testInstant))

        // Act
        val result: PCollection<KV<String, Candle>> = underTest.expand(impulse)

        // Assert
        PAssert.that(result).empty()
        pipeline.run().waitUntilFinish()
    }
}
