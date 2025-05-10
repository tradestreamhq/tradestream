package com.verlumen.tradestream.marketdata

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.coders.CoderRegistry
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.DoFn
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

    // Properly handle transient field by ensuring it's never null
    // Initialize directly instead of in constructor for serialization safety
    @Transient
    private var emittedSymbols: MutableSet<String>? = mutableSetOf()
    
    // Use this to safely synchronize and ensure the set is never null
    private fun getEmittedSymbols(): MutableSet<String> {
        if (emittedSymbols == null) {
            emittedSymbols = mutableSetOf()
        }
        return emittedSymbols!!
    }

    @ProcessElement
    fun process(context: ProcessContext) {
        val inputKv = context.element() as KV<String, Void?>
        val symbol = inputKv.key
        
        // Get a safely initialized set to synchronize on
        val symbols = getEmittedSymbols()
        
        synchronized(symbols) {
            if (!symbols.contains(symbol)) {
                candlesToEmitPerSymbol[symbol]?.forEach { candle ->
                    if (candle.currencyPair == symbol) {
                        context.output(KV.of(symbol, candle))
                    }
                }
                symbols.add(symbol)
            }
        }
    }
    
    companion object { private const val serialVersionUID = 1L }
}


@RunWith(JUnit4::class)
class TiingoCryptoCandleTransformTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @Bind
    @Mock
    private lateinit var mockCurrencyPairSupplier: Supplier<List<CurrencyPair>>

    @Bind
    @Mock
    private lateinit var mockTiingoFetcherFnFactory: TiingoCryptoFetcherFn.Factory

    @Inject
    private lateinit var transformFactory: TiingoCryptoCandleTransform.Factory

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

        // Common mock setups
        `when`(mockCurrencyPairSupplier.get()).thenReturn(currencyPairsList)

        // Create injector with BoundFieldModule and the factory module
        val injector = Guice.createInjector(
            BoundFieldModule.of(this),
            FactoryModuleBuilder()
                .implement(TiingoCryptoCandleTransform::class.java, TiingoCryptoCandleTransform::class.java)
                .build(TiingoCryptoCandleTransform.Factory::class.java)
        )
        
        // Inject fields
        injector.injectMembers(this)

        // Create the instance under test using its Guice-provided factory
        underTest = transformFactory.create(granularity, apiKey)

        // Register coders if necessary
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
        val statefulTestFetcher = StatefulTestTiingoCryptoFetcherFnImpl(granularity, apiKey, candlesToEmitMap)
        `when`(mockTiingoFetcherFnFactory.create(granularity, apiKey)).thenReturn(statefulTestFetcher)

        val expectedOutput: List<KV<String, Candle>> = listOf(
            KV.of(btcUsd.symbol(), candleBtc1),
            KV.of(ethUsd.symbol(), candleEth1)
        )

        // Act
        val result: PCollection<KV<String, Candle>> = underTest.expand(pipeline)

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
