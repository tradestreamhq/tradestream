package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.io.IOException
import java.io.Serializable
import java.util.function.Supplier

@RunWith(JUnit4::class)
class TiingoCryptoCandleTransformTest : Serializable { // Make serializable for Beam

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @get:Rule
    @JvmField
    @Transient // Exclude from serialization
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Mock
    @Bind // Bind the mock HttpClient for injection into TiingoCryptoFetcherFn
    lateinit var mockHttpClient: HttpClient

    // Bind a fake Supplier for currency pairs
    @Bind(to = Supplier::class)
    private val fakeCurrencyPairSupplier: Supplier<List<CurrencyPair>> = FakeCurrencyPairSupplier(listOf("BTC/USD", "ETH/USD"))

    // Inject the transform under test
    @Inject
    lateinit var tiingoTransform: TiingoCryptoCandleTransform

     // Sample Tiingo response for mocking
    private val sampleTiingoResponse = """
       [{"ticker": "%s", "priceData": [
         {"date": "2023-10-27T00:00:00+00:00", "open": 34650, "high": 35000, "low": 34500, "close": 34950, "volume": 1800}
       ]}]
    """.trimIndent()


    @Before
    fun setUp() {
        // Create a test module that includes the bindings and the real FetcherFn
        val testModule = object : AbstractModule() {
            override fun configure() {
                 // This module is needed for the real FetcherFn's dependencies
                 install(BoundFieldModule.of(this@TiingoCryptoCandleTransformTest))
                 // Provide HttpClient binding explicitly if FetcherFn needs it directly
                 bind(HttpClient::class.java).toInstance(mockHttpClient)

            }
        }
        Guice.createInjector(testModule).injectMembers(this)
    }

    @Test
    fun `transform fetches and outputs candles for supplied pairs`() {
        // Arrange: Mock HttpClient responses for each expected ticker
        val btcTicker = "btcusd"
        val ethTicker = "ethusd"
        whenever(mockHttpClient.get(any { it.contains("tickers=$btcTicker") }, any()))
            .thenReturn(sampleTiingoResponse.format(btcTicker))
        whenever(mockHttpClient.get(any { it.contains("tickers=$ethTicker") }, any()))
            .thenReturn(sampleTiingoResponse.format(ethTicker).replace("34950", "2100")) // Simulate different price for ETH


        // Act: Apply the transform to a dummy impulse input
        // We use Create.of(0L) to simulate a single impulse trigger
        val output: PCollection<Candle> = pipeline
            .apply("Impulse", Create.of(0L))
            .apply("FetchTiingoData", tiingoTransform) // Apply the transform


        // Assert: Check the output contains the expected candles
        PAssert.that(output).satisfies(SerializableFunction<Iterable<Candle>, Void?> { candles ->
            val candleList = ImmutableList.copyOf(candles)
            assertThat(candleList).hasSize(2) // Expecting one candle for BTC, one for ETH

            val btcCandle = candleList.find { it.currencyPair == "BTC/USD" }
            val ethCandle = candleList.find { it.currencyPair == "ETH/USD" }

            assertThat(btcCandle).isNotNull()
            assertThat(ethCandle).isNotNull()

            assertThat(btcCandle!!.close).isEqualTo(34950.0)
            assertThat(ethCandle!!.close).isEqualTo(2100.0) // The modified price

            // Verify timestamps (assuming parser works correctly)
            val expectedTimestampMillis = 1698364800000L // 2023-10-27 00:00:00 UTC
            assertThat(Timestamps.toMillis(btcCandle.timestamp)).isEqualTo(expectedTimestampMillis)
            assertThat(Timestamps.toMillis(ethCandle.timestamp)).isEqualTo(expectedTimestampMillis)

            null // PAssert requires Void? return
        })

        // Run the pipeline
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `transform handles http client error gracefully`() {
         // Arrange: Mock HttpClient to throw an error for one of the tickers
        val btcTicker = "btcusd"
        val ethTicker = "ethusd"
        whenever(mockHttpClient.get(any { it.contains("tickers=$btcTicker") }, any()))
            .thenReturn(sampleTiingoResponse.format(btcTicker))
        whenever(mockHttpClient.get(any { it.contains("tickers=$ethTicker") }, any()))
            .thenThrow(IOException("Network Error for ETH"))

         // Act
        val output: PCollection<Candle> = pipeline
            .apply("Impulse", Create.of(0L))
            .apply("FetchTiingoData", tiingoTransform)

        // Assert: Should still output the candle for BTC
         PAssert.that(output).satisfies(SerializableFunction<Iterable<Candle>, Void?> { candles ->
             val candleList = ImmutableList.copyOf(candles)
             assertThat(candleList).hasSize(1) // Only BTC candle expected
             assertThat(candleList[0].currencyPair).isEqualTo("BTC/USD")
             assertThat(candleList[0].close).isEqualTo(34950.0)
             null
         })

        pipeline.run().waitUntilFinish()

    }

    // --- Helper Classes ---

    // Fake Supplier for testing
    class FakeCurrencyPairSupplier(private val pairs: List<String>) : Supplier<List<CurrencyPair>>, Serializable {
         companion object { private const val serialVersionUID = 1L }
        override fun get(): List<CurrencyPair> {
            return pairs.map { CurrencyPair.fromSymbol(it) }
        }
    }

    // Helper to match URLs containing a substring
     private fun contains(substring: String): (String) -> Boolean = { it.contains(substring) }
     // Helper for Mockito argument matching
     private fun <T> any(matcher: (T) -> Boolean): T = org.mockito.kotlin.argThat(matcher)
}
