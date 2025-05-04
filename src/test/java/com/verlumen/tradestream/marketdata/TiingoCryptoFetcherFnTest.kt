package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat // Use Truth for assertions
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.DoFnTester
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.Assert // Keep standard Assert for assertTrue/NotNull if preferred
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatcher
import org.mockito.Mock
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import org.mockito.kotlin.any // Using any() from mockito-kotlin for conciseness
import org.mockito.kotlin.whenever
import java.io.IOException
import java.util.Collections

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock
    lateinit var mockHttpClient: HttpClient

    // Test instances - Manually create with mocks for now
    lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    lateinit var fetcherFnMinute: TiingoCryptoFetcherFn

    private val testApiKey = "TEST_API_KEY_123"

    // Sample responses (remain the same)
    private val sampleResponseDaily = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-26T00:00:00+00:00", "open": 34500, "high": 34800, "low": 34200, "close": 34650, "volume": 1500},
         {"date": "2023-10-27T00:00:00+00:00", "open": 34650, "high": 35000, "low": 34500, "close": 34950, "volume": 1800}
       ]}]
    """.trimIndent()
     private val sampleResponseMinute = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-27T10:01:00+00:00", "open": 34955, "high": 34970, "low": 34950, "close": 34965, "volume": 8.2}
       ]}]
    """.trimIndent()
    private val emptyResponse = "[]"

    @Before
    fun setUp() {
        // Manually instantiate the DoFn with mocks
        fetcherFnDaily = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), testApiKey)
        fetcherFnMinute = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardMinutes(5), testApiKey)
    }

    @Test
    fun `processElement daily fetch uses default start date and outputs KVs`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)

        // Mock HTTP client for initial fetch (daily)
        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher(
            "startDate=$expectedStartDate",
            "resampleFreq=1day",
            "tickers=btcusd",
            "token=$testApiKey"
        )
        Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) },
            Mockito.anyMap())) // Use anyMap() for headers
            .thenReturn(sampleResponseDaily)

        val tester = DoFnTester.of(fetcherFnDaily)
        // Pass input as a list
        val outputs: List<KV<String, Candle>> = tester.processBundle(listOf(input))

        // Use Truth assertions
        assertThat(outputs).isNotNull()
        assertThat(outputs).hasSize(2)
        assertThat(outputs[0].key).isEqualTo(currencyPair)
        assertThat(outputs[0].value.close).isEqualTo(34650.0)
        assertThat(outputs[1].key).isEqualTo(currencyPair)
        assertThat(outputs[1].value.close).isEqualTo(34950.0)
    }

    @Test
    fun `processElement minute fetch uses default start date and correct freq`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)

        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher(
             "startDate=$expectedStartDate",
             "resampleFreq=5min",
             "tickers=btcusd",
             "token=$testApiKey"
        )
         Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) },
            Mockito.anyMap()))
            .thenReturn(sampleResponseMinute)

        val tester = DoFnTester.of(fetcherFnMinute)
        val outputs = tester.processBundle(listOf(input)) // Pass input as a list

        assertThat(outputs).isNotNull()
        assertThat(outputs).hasSize(1)
        assertThat(outputs[0].key).isEqualTo(currencyPair)
        assertThat(outputs[0].value.close).isEqualTo(34965.0)
    }

    @Test
    fun `processElement handles empty api response`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)

        val urlMatcher = UrlMatcher("token=$testApiKey")
         Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) },
            Mockito.anyMap()))
            .thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input)) // Pass input as a list

        assertThat(outputs).isNotNull()
        assertThat(outputs).isEmpty() // Use Truth's isEmpty
    }

    @Test
    fun `processElement skips fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "") // Empty Key

        val tester = DoFnTester.of(fetcherFnInvalidKey)
        val outputs = tester.processBundle(listOf(input)) // Pass input as a list

        assertThat(outputs).isNotNull()
        assertThat(outputs).isEmpty()
        // Verify httpClient.get was *not* called
        Mockito.verify(mockHttpClient, Mockito.never()).get(
            Mockito.anyString(),
            Mockito.anyMap() // Use anyMap()
        )
    }

    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)

        val urlMatcher = UrlMatcher("token=$testApiKey")
         Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) },
            Mockito.anyMap()))
            .thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input)) // Pass input as a list

        assertThat(outputs).isNotNull()
        assertThat(outputs).isEmpty()
    }

    // --- Mockito ArgumentMatcher Implementation ---
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
        override fun toString(): String = "URL containing $substrings"
    }

    // Helper for any() with generics and nullability
    private fun <T> any(): T {
        Mockito.any<T>()
        // Provide a non-null default value (or handle null appropriately if needed)
        // Depending on the type T, this might need adjustment. For Map, emptyMap is safe.
        @Suppress("UNCHECKED_CAST")
        return Collections.emptyMap<String, String>() as T
    }
}
