package com.verlumen.tradestream.marketdata

import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.transforms.DoFnTester
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.Assert
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatcher
import org.mockito.Mock
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
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
        Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg -> urlMatcher.matches(arg) }, 
            Mockito.any()))
            .thenReturn(sampleResponseDaily)

        val tester = DoFnTester.of(fetcherFnDaily)
        // Use varargs processBundle API with an explicit null-safety casting
        val outputs = tester.processBundle(input)

        // For now, we just verify the outputs aren't null or empty
        Assert.assertNotNull("Expected outputs to not be null", outputs)
        Assert.assertTrue("Expected outputs to not be empty", outputs != null && !outputs.isEmpty())
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
        Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg -> urlMatcher.matches(arg) }, 
            Mockito.any()))
            .thenReturn(sampleResponseMinute)

        val tester = DoFnTester.of(fetcherFnMinute)
        val outputs = tester.processBundle(input)

        Assert.assertNotNull("Expected outputs to not be null", outputs)
        Assert.assertTrue("Expected outputs to not be empty", outputs != null && !outputs.isEmpty())
    }

    @Test
    fun `processElement handles empty api response`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)
        
        val urlMatcher = UrlMatcher("token=$testApiKey")
        Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg -> urlMatcher.matches(arg) }, 
            Mockito.any()))
            .thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(input)

        Assert.assertTrue("Expected empty outputs", outputs == null || outputs.isEmpty())
    }

    @Test
    fun `processElement skips fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "")

        val tester = DoFnTester.of(fetcherFnInvalidKey)
        val outputs = tester.processBundle(input)

        Assert.assertTrue("Expected empty outputs", outputs == null || outputs.isEmpty())
        Mockito.verify(mockHttpClient, Mockito.never()).get(
            Mockito.anyString(),
            Mockito.any()
        )
    }

    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)
        
        val urlMatcher = UrlMatcher("token=$testApiKey")
        Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg -> urlMatcher.matches(arg) }, 
            Mockito.any()))
            .thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(input)

        Assert.assertTrue("Expected empty outputs", outputs == null || outputs.isEmpty())
    }

    // --- Mockito ArgumentMatcher Implementation ---
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
        override fun toString(): String = "URL containing $substrings"
    }
}
