package com.verlumen.tradestream.marketdata

import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.DoFnTester
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatcher
import org.mockito.Mock
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import java.io.IOException
import java.util.Arrays
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
        val input = KV.of(currencyPair, null as Void?)

        // Mock HTTP client for initial fetch (daily)
        val expectedStartDate = "2019-01-02"
        // Use standard Mockito when() instead of whenever()
        val urlMatcher = argThat(UrlMatcher(
            "startDate=$expectedStartDate",
            "resampleFreq=1day",
            "tickers=btcusd",
            "token=$testApiKey"
        ))
        Mockito.`when`(mockHttpClient.get(urlMatcher, Collections.emptyMap())).thenReturn(sampleResponseDaily)

        val tester = DoFnTester.of(fetcherFnDaily)
        // Use an array for processBundle
        val outputKVs = tester.processBundle(Arrays.asList(input))

        // Use JUnit assertions instead of Truth
        assertEquals("Expected 2 output elements", 2, outputKVs.size)
        
        // For first result
        val firstResult = outputKVs[0]
        assertEquals("Expected currency pair to match", currencyPair, firstResult.getKey())
        assertEquals("Expected close price to match", 34650.0, firstResult.getValue().close, 0.001)
        
        // For second result
        val secondResult = outputKVs[1]
        assertEquals("Expected currency pair to match", currencyPair, secondResult.getKey())
        assertEquals("Expected close price to match", 34950.0, secondResult.getValue().close, 0.001)
    }

    @Test
    fun `processElement minute fetch uses default start date and correct freq`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        val expectedStartDate = "2019-01-02"
        val urlMatcher = argThat(UrlMatcher(
             "startDate=$expectedStartDate",
             "resampleFreq=5min",
             "tickers=btcusd",
             "token=$testApiKey"
        ))
        Mockito.`when`(mockHttpClient.get(urlMatcher, Collections.emptyMap())).thenReturn(sampleResponseMinute)

        val tester = DoFnTester.of(fetcherFnMinute)
        val outputKVs = tester.processBundle(Arrays.asList(input))

        // Use JUnit assertions
        assertEquals("Expected 1 output element", 1, outputKVs.size)
        val result = outputKVs[0]
        assertEquals("Expected currency pair to match", currencyPair, result.getKey())
        assertEquals("Expected close price to match", 34965.0, result.getValue().close, 0.001)
    }

    @Test
    fun `processElement handles empty api response`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val urlMatcher = argThat(UrlMatcher("token=$testApiKey"))
        Mockito.`when`(mockHttpClient.get(urlMatcher, Collections.emptyMap())).thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputKVs = tester.processBundle(Arrays.asList(input))

        assertTrue("Expected empty result list", outputKVs.isEmpty())
    }

    @Test
    fun `processElement skips fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "")

        val tester = DoFnTester.of(fetcherFnInvalidKey)
        val outputKVs = tester.processBundle(Arrays.asList(input))

        assertTrue("Expected empty result list", outputKVs.isEmpty())
        Mockito.verify(mockHttpClient, Mockito.never()).get(
            Mockito.anyString(),
            Mockito.<Map<String, String>>anyMap()
        )
    }

    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val urlMatcher = argThat(UrlMatcher("token=$testApiKey"))
        Mockito.`when`(mockHttpClient.get(urlMatcher, Collections.emptyMap())).thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputKVs = tester.processBundle(Arrays.asList(input))

        assertTrue("Expected empty result list", outputKVs.isEmpty())
    }

    // --- Standard Mockito ArgumentMatcher Implementation ---
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
        override fun toString(): String = "URL containing $substrings"
    }

    // Helper function to use the standard Mockito matcher
    private fun <T> argThat(matcher: ArgumentMatcher<T>): T {
        return Mockito.argThat<T> { arg -> matcher.matches(arg as Any) }
    }
}
