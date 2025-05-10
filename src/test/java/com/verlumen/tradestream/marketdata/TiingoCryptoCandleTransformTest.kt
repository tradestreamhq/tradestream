package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.assistedinject.FactoryModuleBuilder // For assisted inject of TiingoCryptoCandleTransform
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
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.Serializable
import java.util.function.Supplier // Standard Java Supplier
import com.verlumen.tradestream.http.HttpClient // Import HttpClient
import org.mockito.Mockito // Import Mockito for mocking HttpClient

// --- Test Doubles for Dependencies ---
// (SerializableTestFetcherFnFactory, SerializableTestFetcherFn, SerializableTestCurrencyPairSupplier remain the same as in the previous good answer)

/**
 * A serializable test implementation of TiingoCryptoFetcherFn.Factory.
 */
class SerializableTestFetcherFnFactory(
    private val responses: Map<String, Candle>
) : TiingoCryptoFetcherFn.Factory, Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }
    override fun create(granularity: Duration, apiKey: String): TiingoCryptoFetcherFn {
        // HttpClient can be mocked here if TiingoCryptoFetcherFn directly uses it
        // For this test structure, the mock HTTP client isn't strictly necessary
        // if SerializableTestFetcherFn doesn't use it.
        val mockHttpClient = Mockito.mock(HttpClient::class.java)
        return SerializableTestFetcherFn(mockHttpClient, granularity, apiKey, responses)
    }
}

/**
 * A serializable test implementation of TiingoCryptoFetcherFn.
 * It now takes the responses map in its constructor.
 */
class SerializableTestFetcherFn(
    // HttpClient is a dependency of the real TiingoCryptoFetcherFn,
    // so our test double should also accept it, even if it doesn't use it directly.
    @Suppress("UNUSED_PARAMETER") httpClient: HttpClient,
    @Suppress("UNUSED_PARAMETER") granularity: Duration,
    @Suppress("UNUSED_PARAMETER") apiKey: String,
    private val responses: Map<String, Candle> // Added to constructor
) : TiingoCryptoFetcherFn(httpClient, granularity, apiKey), Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    @ProcessElement
    fun processElement(c: ProcessContext) {
        val currencyPairSymbol = c.element().key // Input is KV<String, Void?> after GroupByKey and Unwrap
        val candle = responses[currencyPairSymbol]
        if (candle != null) {
            c.output(KV.of(currencyPairSymbol, candle))
        }
    }
}

/**
 * A serializable currency pair supplier for testing.
 */
class SerializableTestCurrencyPairSupplier(
    private val pairs: List<CurrencyPair>
) : Supplier<List<CurrencyPair>>, Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }
    override fun get(): List<CurrencyPair> = pairs
}


@RunWith(JUnit4::class)
class TiingoCryptoCandleTransformTest : Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    @get:Rule
    @Transient // Important for Beam tests
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // --- Test Data ---
    private val btcPair = CurrencyPair.fromSymbol("BTC/USD")
    private val ethPair = CurrencyPair.fromSymbol("ETH/USD")
    private val defaultTestCurrencyPairs = listOf(btcPair, ethPair)
    private val defaultTestApiKey = "DEFAULT_TEST_API_KEY"
    private val defaultTestGranularity = Duration.standardMinutes(1)

    // --- Injected by Guice ---
    @Inject
    @Transient // Beam PTransforms should ideally not be stateful test class members for direct injection if they are complex.
              // However, for assisted inject of the transform itself, this is okay for test setup.
    private lateinit var transformFactory: TiingoCryptoCandleTransform.Factory
    private lateinit var transform: TiingoCryptoCandleTransform // This will be created by the factory

    // --- Test Doubles for Guice Module ---
    // These will be configured per test if needed, or use defaults.
    private var currencyPairSupplierInstance: Supplier<List<CurrencyPair>> = SerializableTestCurrencyPairSupplier(defaultTestCurrencyPairs)
    private var fetcherFnFactoryInstance: TiingoCryptoFetcherFn.Factory = SerializableTestFetcherFnFactory(emptyMap())


    // --- Guice Test Module ---
    private inner class TestModule : AbstractModule() {
        override fun configure() {
            // Bind the Supplier<List<CurrencyPair>> to our test double instance
            @Suppress("UNCHECKED_CAST") // Safe due to type erasure and control over instance
            bind(Supplier::class.java as Class<Supplier<List<CurrencyPair>>>)
                .toInstance(currencyPairSupplierInstance)

            // Bind the TiingoCryptoFetcherFn.Factory to our test double instance
            bind(TiingoCryptoFetcherFn.Factory::class.java)
                .toInstance(fetcherFnFactoryInstance)
            
            // Bind HttpClient to a mock as it's a dependency of the real TiingoCryptoFetcherFn
            // and our SerializableTestFetcherFn constructor now expects it.
             bind(HttpClient::class.java).toInstance(Mockito.mock(HttpClient::class.java))


            // Install the factory for TiingoCryptoCandleTransform (which has @Assisted inject)
            install(
                FactoryModuleBuilder()
                    .build(TiingoCryptoCandleTransform.Factory::class.java)
            )
        }
    }

    @Before
    fun setUp() {
        // Default setup for currencyPairSupplierInstance and fetcherFnFactoryInstance
        // can be done here if not overridden by specific tests.
        // For example, to reset to a default state for each test:
        currencyPairSupplierInstance = SerializableTestCurrencyPairSupplier(defaultTestCurrencyPairs)
        fetcherFnFactoryInstance = SerializableTestFetcherFnFactory(emptyMap()) // Default to no responses

        val injector = Guice.createInjector(TestModule(), BoundFieldModule.of(this))
        injector.injectMembers(this)

        // Create the transform instance using the injected factory and default parameters
        transform = transformFactory.create(defaultTestGranularity, defaultTestApiKey)
    }

    private fun createTestCandle(symbol: String, closePrice: Double): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(symbol)
            .setOpen(closePrice - 10.0)
            .setHigh(closePrice + 5.0)
            .setLow(closePrice - 15.0)
            .setClose(closePrice)
            .setVolume(10.0)
            .setTimestamp(com.google.protobuf.util.Timestamps.fromMillis(System.currentTimeMillis()))
            .build()
    }

    @Test
    fun `transform fetches and outputs candles for supplied pairs`() {
        val testResponses = mapOf(
            "BTC/USD" to createTestCandle("BTC/USD", 34965.0),
            "ETH/USD" to createTestCandle("ETH/USD", 2002.0)
        )
        // Configure the fetcher factory for this specific test
        fetcherFnFactoryInstance = SerializableTestFetcherFnFactory(testResponses)
        // Re-create the transform with the new factory instance (or re-inject if setup allows)
        // For simplicity here, we'll re-create it. A more advanced setup might re-initialize Guice or use providers.
         val specificTransform = transformFactory.create(defaultTestGranularity, defaultTestApiKey)


        val impulse = pipeline.apply("CreateImpulse", Create.of(Instant.now()))
        val output: PCollection<KV<String, Candle>> = impulse.apply("RunActualTransform", specificTransform)

        PAssert.that(output).satisfies(SerializableFunction<Iterable<KV<String, Candle>>, Void?> { kvs ->
            val kvList = kvs.toList()
            assertThat(kvList).hasSize(2)
            val btcCandle = kvList.find { it.key == "BTC/USD" }
            val ethCandle = kvList.find { it.key == "ETH/USD" }
            assertThat(btcCandle).isNotNull()
            assertThat(ethCandle).isNotNull()
            assertThat(btcCandle!!.value.close).isEqualTo(34965.0)
            assertThat(ethCandle!!.value.close).isEqualTo(2002.0)
            null
        })

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `transform handles error for one pair and succeeds for another`() {
        val testResponses = mapOf(
            "BTC/USD" to createTestCandle("BTC/USD", 34965.0)
            // ETH/USD intentionally omitted
        )
        fetcherFnFactoryInstance = SerializableTestFetcherFnFactory(testResponses)
        currencyPairSupplierInstance = SerializableTestCurrencyPairSupplier(listOf(btcPair, ethPair)) // Ensure both are supplied
        val specificTransform = transformFactory.create(defaultTestGranularity, defaultTestApiKey)
        
        val impulse = pipeline.apply("CreateImpulseForErrorTest", Create.of(Instant.now()))
        val output: PCollection<KV<String, Candle>> = impulse.apply("RunTransformWithErrorSim", specificTransform)

        PAssert.that(output).satisfies(SerializableFunction<Iterable<KV<String, Candle>>, Void?> { kvs ->
            val kvList = kvs.toList()
            assertThat(kvList).hasSize(1) // Only BTC candle expected
            assertThat(kvList[0].key).isEqualTo("BTC/USD")
            assertThat(kvList[0].value.close).isEqualTo(34965.0)
            null
        })

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `expand with pipeline with specific granularity and api key`() {
        val specificGranularity = Duration.standardHours(1)
        val specificApiKey = "SPECIFIC_KEY"

        // Ensure no responses are set for this test to verify impulse setup
        fetcherFnFactoryInstance = SerializableTestFetcherFnFactory(emptyMap())
        currencyPairSupplierInstance = SerializableTestCurrencyPairSupplier(defaultTestCurrencyPairs)

        // Use the main transform instance created in setUp, but re-create it if parameters change
        // For this test, we are testing the `expand(Pipeline)` method of a *new* instance
        val specificTransform = TiingoCryptoCandleTransform(
            currencyPairSupplierInstance,
            fetcherFnFactoryInstance,
            specificGranularity,
            specificApiKey
        )
        
        // The expand(Pipeline) method sets up its own PeriodicImpulse
        val output: PCollection<KV<String, Candle>> = specificTransform.expand(pipeline)
        
        // Expect empty output because the test fetcher is configured with no responses
        PAssert.that(output).empty()
        
        pipeline.run().waitUntilFinish()
    }
}
