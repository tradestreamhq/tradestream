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
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import java.io.IOException
import java.io.Serializable
import java.util.function.Supplier

@RunWith(JUnit4::class)
class TiingoCryptoCandleTransformTest : Serializable {
    private val serialVersionUID = 1L

    @get:Rule
    @Transient // Exclude from serialization by Beam
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    @get:Rule
    @Transient
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock
    @Transient
    lateinit var mockHttpClient: HttpClient

    @Mock
    @Transient
    lateinit var mockCurrencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>

    // The DoFn will be created manually with mocked dependencies for this test PR
    lateinit var testFetcherFn: TiingoCryptoFetcherFn
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
        // Manually create the TiingoCryptoFetcherFn with its dependencies mocked or faked
        testFetcherFn = TiingoCryptoFetcherFn(mockHttpClient, testGranularity, testApiKey)

        // Manually create the transform with the mocked supplier and the test FetcherFn
        transform = TiingoCryptoCandleTransform(mockCurrencyPairSupplier, testFetcherFn)

        whenever(mockCurrencyPairSupplier.get()).thenReturn(listOf(btcPair, ethPair))
    }

    @Test
    fun `transform fetches and outputs candles for supplied pairs`() {
        // Arrange: Mock HttpClient responses
        val btcTicker = "btcusd"
        val ethTicker = "ethusd"
        val urlMatcherBtc = UrlMatcher("tickers=$btcTicker", "token=$testApiKey")
        val urlMatcherEth = UrlMatcher("tickers=$ethTicker", "token=$testApiKey")

        whenever(mockHttpClient.get(argThat(urlMatcherBtc), Mockito.anyMap())).thenReturn(sampleBtcResponse)
        whenever(mockHttpClient.get(argThat(urlMatcherEth), Mockito.anyMap())).thenReturn(sampleEthResponse)

        // Act: Apply the transform to a dummy impulse input - using Instant instead of Long
        val now = Instant.now()
        val impulse: PCollection<Instant> = pipeline.apply("CreateImpulse", Create.of(now))
        val output: PCollection<KV<String, Candle>> = impulse.apply("RunTiingoTransform", transform)

        // Assert
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

        // Verify supplier was called
        verify(mockCurrencyPairSupplier).get()
        // Verify HTTP client was called for both tickers
        verify(mockHttpClient).get(argThat(urlMatcherBtc), Mockito.anyMap())
        verify(mockHttpClient).get(argThat(urlMatcherEth), Mockito.anyMap())
    }

    @Test
    fun `transform handles http client error for one pair`() {
        val btcTicker = "btcusd"
        val ethTicker = "ethusd"
        val urlMatcherBtc = UrlMatcher("tickers=$btcTicker")
        val urlMatcherEth = UrlMatcher("tickers=$ethTicker")

        whenever(mockHttpClient.get(argThat(urlMatcherBtc), Mockito.anyMap())).thenReturn(sampleBtcResponse)
        whenever(mockHttpClient.get(argThat(urlMatcherEth), Mockito.anyMap())).thenThrow(IOException("Network Error for ETH"))

        // Using Instant instead of Long
        val now = Instant.now()
        val impulse: PCollection<Instant> = pipeline.apply("CreateImpulse", Create.of(now))
        val output: PCollection<KV<String, Candle>> = impulse.apply("RunTiingoTransform", transform)

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
        // This test is more conceptual as testing PeriodicImpulse end-to-end is complex in unit tests.
        // We'll verify the structure by checking if the transform can be applied.
        // Mock the actual fetching part to avoid external calls.
        whenever(mockHttpClient.get(Mockito.anyString(), Mockito.anyMap())).thenReturn("[]") // Return empty to avoid parsing errors

        val output: PCollection<KV<String, Candle>> = transform.expand(pipeline) // Use the convenience method

        PAssert.that(output).empty() // Expect empty because we mocked an empty response
        pipeline.run().waitUntilFinish()
        // If it runs without pipeline construction errors, it's a good sign.
    }

    // Standard Mockito ArgumentMatcher Implementation
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
        override fun toString(): String = "URL containing $substrings"
    }

    private fun argThat(matcher: ArgumentMatcher<String>): String {
        return Mockito.argThat(matcher) ?: ""
    }
}
