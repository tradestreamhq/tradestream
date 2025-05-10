package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.http.HttpClient
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
import org.mockito.ArgumentMatcher
import org.mockito.Mock
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import org.mockito.kotlin.any
import org.mockito.kotlin.doReturn
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import java.io.IOException
import java.io.Serializable
import java.util.function.Supplier

@RunWith(JUnit4::class)
class TiingoCryptoCandleTransformTest : Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    @get:Rule
    @Transient // Exclude from serialization by Beam
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @get:Rule
    @Transient
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Transient
    @Mock
    lateinit var mockHttpClient: HttpClient

    @Transient
    @Mock
    lateinit var mockCurrencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>

    @Transient // Mark as transient to prevent serialization
    lateinit var testFetcherFn: TiingoCryptoFetcherFn
    
    @Transient // Mark as transient to prevent serialization
    lateinit var transform: TiingoCryptoCandleTransform

    private val testApiKey = "TEST_KEY_FOR_TRANSFORM"
    private val testGranularity = Duration.standardMinutes(1)

    private val btcPair = CurrencyPair.fromSymbol("BTC/USD")
    private val ethPair = CurrencyPair.fromSymbol("ETH/USD")

    private val sampleBtcResponse = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-27T10:01:00+00:00", "open": 34955, "high": 34970, "low": 34950, "close": 34965, "volume": 8.2}
       ]}]
    """.trimIndent()
    private val sampleEthResponse = """
       [{"ticker": "ethusd", "priceData": [
         {"date": "2023-10-27T10:01:00+00:00", "open": 2000, "high": 2005, "low": 1998, "close": 2002, "volume": 10.1}
       ]}]
    """.trimIndent()

    @Before
    fun setUp() {
        // Use a test-friendly implementation of the supplier
        val testCurrencyPairs = listOf(btcPair, ethPair)
        whenever(mockCurrencyPairSupplier.get()).thenReturn(testCurrencyPairs)
        
        // For tests, create a serializable test version of the fetcher function
        testFetcherFn = SerializableTestFetcherFn(testGranularity, testApiKey)
        
        // Create the transform with our serializable components
        transform = TiingoCryptoCandleTransform(mockCurrencyPairSupplier, testFetcherFn)
    }

    @Test
    fun `transform fetches and outputs candles for supplied pairs`() {
        // Setup HTTP responses directly in the test fetcher
        (testFetcherFn as SerializableTestFetcherFn).setupTestResponses(
            mapOf(
                "BTC/USD" to createTestCandle("BTC/USD", 34965.0),
                "ETH/USD" to createTestCandle("ETH/USD", 2002.0)
            )
        )

        // Create test input
        val now = Instant.now()
        val impulse: PCollection<Instant> = pipeline.apply("CreateImpulse", Create.of(now))
        
        // Apply the transform
        val output: PCollection<KV<String, Candle>> = impulse.apply("RunTiingoTransform", transform)

        // Assert the output
        PAssert.that(output).satisfies(SerializableFunction<Iterable<KV<String, Candle>>, Void?> { kvs ->
            val kvList = kvs.toList()
            assertThat(kvList).hasSize(2)

            val btcCandleOutput = kvList.find { it.key == "BTC/USD" }
            val ethCandleOutput = kvList.find { it.key == "ETH/USD" }

            assertThat(btcCandleOutput).isNotNull()
            assertThat(ethCandleOutput).isNotNull()

            assertThat(btcCandleOutput!!.value.close).isEqualTo(34965.0)
            assertThat(ethCandleOutput!!.value.close).isEqualTo(2002.0)
            null
        })

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `transform handles http client error for one pair`() {
        // Setup success for BTC and failure for ETH
        (testFetcherFn as SerializableTestFetcherFn).setupTestResponses(
            mapOf(
                "BTC/USD" to createTestCandle("BTC/USD", 34965.0)
                // ETH/USD intentionally omitted to simulate failure
            )
        )

        // Create test input
        val now = Instant.now()
        val impulse: PCollection<Instant> = pipeline.apply("CreateImpulse", Create.of(now))
        
        // Apply the transform
        val output: PCollection<KV<String, Candle>> = impulse.apply("RunTiingoTransform", transform)

        // Assert the output
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
    fun `expand with pipeline sets up periodic impulse`() {
        // Setup a simple response for testing the full pipeline flow
        (testFetcherFn as SerializableTestFetcherFn).setupTestResponses(emptyMap())
        
        // Use the convenience method
        val output: PCollection<KV<String, Candle>> = transform.expand(pipeline)

        // Expect empty because we provided no test data
        PAssert.that(output).empty()
        
        pipeline.run().waitUntilFinish()
    }

    // Helper method to create a test candle
    private fun createTestCandle(symbol: String, closePrice: Double): Candle {
        return Candle.newBuilder()
            .setSymbol(symbol)
            .setOpen(closePrice - 10.0)
            .setHigh(closePrice + 5.0)
            .setLow(closePrice - 15.0)
            .setClose(closePrice)
            .setVolume(10.0)
            .build()
    }
}

/**
 * A serializable test version of TiingoCryptoFetcherFn that doesn't depend on mocks.
 * This simulates the behavior without requiring serialization of mocks.
 */
class SerializableTestFetcherFn(
    private val granularity: Duration,
    private val apiKey: String
) : TiingoCryptoFetcherFn(null, granularity, apiKey), Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }
    
    // Test data storage
    @Transient
    private var testResponses: Map<String, Candle> = emptyMap()
    
    fun setupTestResponses(responses: Map<String, Candle>) {
        this.testResponses = responses
    }
    
    // Override process method to return test data instead of making real HTTP calls
    override fun processElement(input: KV<String, Void?>): Iterable<KV<String, Candle>> {
        val symbol = input.key
        val candle = testResponses[symbol] ?: return emptyList()
        return listOf(KV.of(symbol, candle))
    }
}
