package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.coders.VoidCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
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
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.io.IOException

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock
    lateinit var mockHttpClient: HttpClient

    // Test instances
    lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    lateinit var fetcherFnMinute: TiingoCryptoFetcherFn

    private val testApiKey = "TEST_API_KEY_123"

    // Sample responses
    private val sampleResponseDailyPage1 = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-26T00:00:00+00:00", "open": 34500, "high": 34800, "low": 34200, "close": 34650, "volume": 1500},
         {"date": "2023-10-27T00:00:00+00:00", "open": 34650, "high": 35000, "low": 34500, "close": 34950, "volume": 1800}
       ]}]
    """.trimIndent()
    
    private val sampleResponseDailyPage2 = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-28T00:00:00+00:00", "open": 34950, "high": 35200, "low": 34800, "close": 35100, "volume": 1200}
       ]}]
    """.trimIndent()
    
    private val sampleResponseMinutePage1 = """
       [{"ticker": "ethusd", "priceData": [
         {"date": "2023-10-27T10:01:00+00:00", "open": 2000, "high": 2002, "low": 1999, "close": 2001, "volume": 5.2}
       ]}]
    """.trimIndent()
    
    private val sampleResponseMinutePage2 = """
       [{"ticker": "ethusd", "priceData": [
         {"date": "2023-10-27T10:02:00+00:00", "open": 2001, "high": 2005, "low": 2000, "close": 2004, "volume": 6.1}
       ]}]
    """.trimIndent()
    
    private val emptyResponse = "[]"

    @Before
    fun setUp() {
        fetcherFnDaily = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), testApiKey)
        fetcherFnMinute = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardMinutes(1), testApiKey)
    }

    @Test
    fun `initial fetch uses default start date`() {
        val currencyPair = "BTC/USD"
        
        // Mock HTTP client to verify default start date
        val urlMatcher = UrlMatcher("startDate=2019-01-02", "resampleFreq=1day", "tickers=btcusd")
        whenever(mockHttpClient.get(argThat(urlMatcher), any())).thenReturn(sampleResponseDailyPage1)
        
        // Setup pipeline
        val input = pipeline.apply(Create.of(KV.of(currencyPair, null as Void?)))
        val output = input.apply(ParDo.of(fetcherFnDaily))
        
        // Verify output
        PAssert.that(output).satisfies { results ->
            val list = results.toList()
            assertThat(list).hasSize(2)
            assertThat(list[0].key).isEqualTo(currencyPair)
            assertThat(list[0].value.close).isEqualTo(34650.0)
            assertThat(list[1].value.close).isEqualTo(34950.0)
            null
        }
        
        pipeline.run()
    }

    @Test
    fun `initial fetch with empty response produces no output`() {
        val currencyPair = "BTC/USD"
        
        // Mock empty response
        val urlMatcher = UrlMatcher("startDate=2019-01-02")
        whenever(mockHttpClient.get(argThat(urlMatcher), any())).thenReturn(emptyResponse)
        
        // Setup pipeline
        val input = pipeline.apply(Create.of(KV.of(currencyPair, null as Void?)))
        val output = input.apply(ParDo.of(fetcherFnDaily))
        
        // Verify no output
        PAssert.that(output).empty()
        
        pipeline.run()
    }

    @Test
    fun `stateful incremental fetching with TestStream`() {
        val currencyPair = "BTC/USD"
        
        // Create a serializable mock HTTP client
        val mockHttpClient = Mockito.mock(
            HttpClient::class.java,
            Mockito.withSettings().serializable()
        )
        
        // First response - initial load with default start date
        val initialUrlMatcher = UrlMatcher("startDate=2019-01-02", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(Mockito.argThat(initialUrlMatcher), Mockito.anyMap()))
            .thenReturn(sampleResponseDailyPage1)
        
        // Second response - incremental load with date based on previous state
        val incrementalUrlMatcher = UrlMatcher("startDate=2023-10-28", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(Mockito.argThat(incrementalUrlMatcher), Mockito.anyMap()))
            .thenReturn(sampleResponseDailyPage2)
        
        // Create the DoFn to test
        val fetcherFn = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), testApiKey)
        
        // Create the TestStream with events and timing
        val testStream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), VoidCoder.of()))
            .addElements(KV.of(currencyPair, null as Void?))  // First fetch
            .advanceProcessingTime(Duration.standardHours(1)) // Advance time
            .addElements(KV.of(currencyPair, null as Void?))  // Second fetch
            .advanceWatermarkToInfinity()
        
        // Create and run the pipeline
        val input = pipeline.apply(testStream)
        val output = input.apply(ParDo.of(fetcherFn))
        
        // Verify output with correct assertions
        PAssert.that(output).satisfies { results ->
            val candles = results.toList()
            
            // Should have 3 candles in total (2 from first response, 1 from second)
            assertThat(candles).hasSize(3)
            
            // All candles should have the right key
            assertThat(candles.all { it.key == currencyPair }).isTrue()
            
            // Verify close prices from the samples
            val closePrices = candles.map { it.value.close }.toSet()
            assertThat(closePrices).containsExactly(34650.0, 34950.0, 35100.0)
            
            null
        }
        
        pipeline.run()
    }

    @Test
    fun `skip fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "")
        
        // Setup pipeline
        val input = pipeline.apply(Create.of(KV.of(currencyPair, null as Void?)))
        val output = input.apply(ParDo.of(fetcherFnInvalidKey))
        
        // Verify no output
        PAssert.that(output).empty()
        
        pipeline.run()
        
        // Verify HTTP client was never called
        Mockito.verify(mockHttpClient, Mockito.never()).get(any(), any())
    }

    @Test
    fun `handle http error gracefully`() {
        val currencyPair = "BTC/USD"
        
        // Mock HTTP client to throw exception
        whenever(mockHttpClient.get(any(), any())).thenThrow(IOException("Network Error"))
        
        // Setup pipeline
        val input = pipeline.apply(Create.of(KV.of(currencyPair, null as Void?)))
        val output = input.apply(ParDo.of(fetcherFnDaily))
        
        // Verify no output
        PAssert.that(output).empty()
        
        pipeline.run()
    }

    // Helper URL matcher class
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
    }
    
    // Helper to use standard Mockito matcher syntax
    private fun argThat(matcher: ArgumentMatcher<String>): String {
        return Mockito.argThat(matcher) ?: ""
    }
    
    // Helper for anyMap()
    private fun <K, V> anyMap(): Map<K, V> {
        Mockito.anyMap<K, V>()
        @Suppress("UNCHECKED_CAST")
        return emptyMap<K, V>() as Map<K, V>
    }
}
