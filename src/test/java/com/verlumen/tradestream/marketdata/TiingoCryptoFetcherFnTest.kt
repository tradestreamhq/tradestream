package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
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
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatcher
import org.mockito.Mock
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import java.io.IOException

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
        Mockito.`when`(mockHttpClient.get(urlMatcher, emptyMap())).thenReturn(sampleResponseDaily)

        val tester = DoFnTester.of(fetcherFnDaily)
        // Fix processBundle call by using vararg
        val outputKVs = tester.processBundle(input)

        // Fix assertion chain with correct methods
        assertThat(outputKVs.size).isEqualTo(2)
        val firstResult = outputKVs[0]
        assertThat(firstResult.key).isEqualTo(currencyPair)
        assertThat(firstResult.value.close).isEqualTo(34650.0)
        val secondResult = outputKVs[1]
        assertThat(secondResult.key).isEqualTo(currencyPair)
        assertThat(secondResult.value.close).isEqualTo(34950.0)
    }

    @Test
    fun `processElement minute fetch uses default start date and correct freq`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        val expectedStartDate = "2019-01-02"
         // Use standard Mockito when() instead of whenever()
        val urlMatcher = argThat(UrlMatcher(
             "startDate=$expectedStartDate",
             "resampleFreq=5min",
             "tickers=btcusd",
             "token=$testApiKey"
        ))
        Mockito.`when`(mockHttpClient.get(urlMatcher, emptyMap())).thenReturn(sampleResponseMinute)

        val tester = DoFnTester.of(fetcherFnMinute) // Use 5-min fetcher
        val outputKVs = tester.processBundle(input)

        // Fix assertion chain with correct methods
        assertThat(outputKVs.size).isEqualTo(1)
        val result = outputKVs[0]
        assertThat(result.key).isEqualTo(currencyPair)
        assertThat(result.value.close).isEqualTo(34965.0)
    }


    @Test
    fun `processElement handles empty api response`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val urlMatcher = argThat(UrlMatcher("token=$testApiKey")) // Ensure key is still passed
        Mockito.`when`(mockHttpClient.get(urlMatcher, emptyMap())).thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputKVs = tester.processBundle(input)

        assertThat(outputKVs).isEmpty()
    }

     @Test
    fun `processElement skips fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "") // Empty Key

        val tester = DoFnTester.of(fetcherFnInvalidKey)
        val outputKVs = tester.processBundle(input)

        assertThat(outputKVs).isEmpty()
        // Fix verify with correct Mockito syntax using matchers
        Mockito.verify(mockHttpClient, Mockito.never()).get(Mockito.anyString(), Mockito.anyMap())
    }

    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val urlMatcher = argThat(UrlMatcher("token=$testApiKey"))
        Mockito.`when`(mockHttpClient.get(urlMatcher, emptyMap())).thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputKVs = tester.processBundle(input)

        assertThat(outputKVs).isEmpty()
    }

    // --- Standard Mockito ArgumentMatcher Implementation ---
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
        override fun toString(): String = "URL containing $substrings"
    }

    // Helper function to use the standard Mockito matcher
    private fun argThat(matcher: ArgumentMatcher<String>): String {
        return Mockito.argThat(matcher) ?: "" // Use Mockito's argThat
    }
}
