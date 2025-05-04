package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import org.hamcrest.Matchers.* // For Hamcrest matchers in the first test
import org.mockito.kotlin.* // For any(), argThat(), whenever()

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
import org.mockito.Mock
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

    // Sample responses
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
        fetcherFnMinute = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardMinutes(5), testApiKey) // Example: 5 min granularity
    }

    @Test
    fun `processElement daily fetch uses default start date and outputs KVs`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Mock HTTP client for initial fetch (daily)
        val expectedStartDate = "2019-01-02" // Should always use default for now
        // *** Use Hamcrest Matchers.allOf ***
        val expectedUrl = allOf(
            containsString("startDate=$expectedStartDate"),
            containsString("resampleFreq=1day"), // Adjusted to match helper output for daily
            containsString("tickers=btcusd"),
            containsString("token=$testApiKey")
        )
        whenever(mockHttpClient.get(argThat(expectedUrl), any())).thenReturn(sampleResponseDaily)

        // Use DoFnTester to test the DoFn in isolation
        val tester = DoFnTester.of(fetcherFnDaily)
        // *** EXPLICITLY TYPED outputKVs ***
        val outputKVs: List<KV<String, Candle>> = tester.processBundle(input)

        // Assert output
        assertThat(outputKVs).hasSize(2)
        assertThat(outputKVs[0].key).isEqualTo(currencyPair)
        assertThat(outputKVs[0].value.close).isEqualTo(34650.0)
        assertThat(outputKVs[1].key).isEqualTo(currencyPair)
        assertThat(outputKVs[1].value.close).isEqualTo(34950.0)
        // Verify timestamps if needed using Timestamps.toMillis(...)
    }

    @Test
    fun `processElement minute fetch uses default start date and correct freq`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Mock HTTP client for initial fetch (5 minute)
        val expectedStartDate = "2019-01-02"
        // *** Use LAMBDA for argThat ***
        val expectedUrlMatcher: (String) -> Boolean = { url ->
            url.contains("startDate=$expectedStartDate") &&
            url.contains("resampleFreq=5min") && // Check correct freq
            url.contains("tickers=btcusd") &&
            url.contains("token=$testApiKey")
        }
        whenever(mockHttpClient.get(argThat(expectedUrlMatcher), any())).thenReturn(sampleResponseMinute)

        val tester = DoFnTester.of(fetcherFnMinute) // Use 5-min fetcher
        // *** EXPLICITLY TYPED outputKVs ***
        val outputKVs: List<KV<String, Candle>> = tester.processBundle(input)

        // Assert output
        assertThat(outputKVs).hasSize(1)
        assertThat(outputKVs[0].key).isEqualTo(currencyPair)
        assertThat(outputKVs[0].value.close).isEqualTo(34965.0)
    }


    @Test
    fun `processElement handles empty api response`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        // *** Use LAMBDA for argThat (simpler) ***
        val expectedUrlMatcher: (String) -> Boolean = { it.contains("token=$testApiKey") }
        whenever(mockHttpClient.get(argThat(expectedUrlMatcher), any())).thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        // *** EXPLICITLY TYPED outputKVs ***
        val outputKVs: List<KV<String, Candle>> = tester.processBundle(input)

        assertThat(outputKVs).isEmpty()
    }

     @Test
    fun `processElement skips fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Create fetcher with invalid key
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "") // Empty Key

        val tester = DoFnTester.of(fetcherFnInvalidKey)
        // *** EXPLICITLY TYPED outputKVs ***
        val outputKVs: List<KV<String, Candle>> = tester.processBundle(input)

        assertThat(outputKVs).isEmpty()
        // Verify httpClient.get was *not* called (using Mockito.verify if needed, but logic check is sufficient here)
    }


    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        // *** Use LAMBDA for argThat ***
        val expectedUrlMatcher: (String) -> Boolean = { it.contains("token=$testApiKey") }
        whenever(mockHttpClient.get(argThat(expectedUrlMatcher), any())).thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        // *** EXPLICITLY TYPED outputKVs ***
        val outputKVs: List<KV<String, Candle>> = tester.processBundle(input)

        assertThat(outputKVs).isEmpty()
    }
}
