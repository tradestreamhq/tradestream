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
import java.io.Serializable

/**
 * A serializable HttpClient implementation for testing
 */
class SerializableHttpClient : Serializable, HttpClient {
    private val serialVersionUID = 1L
    
    // Maps for storing configured responses and exceptions
    private val responseMap = HashMap<String, String>()
    private val exceptionMap = HashMap<String, Exception>()
    
    // Configure a response for a URL containing the given pattern
    fun setResponse(urlPattern: String, response: String) {
        responseMap[urlPattern] = response
    }
    
    // Configure an exception to be thrown for a URL containing the given pattern
    fun setException(urlPattern: String, exception: Exception) {
        exceptionMap[urlPattern] = exception
    }
    
    override fun get(url: String, headers: Map<String, String>): String {
        // Check if we should throw an exception
        for ((pattern, exception) in exceptionMap) {
            if (url.contains(pattern)) {
                throw exception
            }
        }
        
        // Look for a matching response
        for ((pattern, response) in responseMap) {
            if (url.contains(pattern)) {
                return response
            }
        }
        
        // Default empty response
        return "[]"
    }
    
    // Implement post method (it is required by the interface)
    override fun post(url: String, body: String, headers: Map<String, String>): String {
        throw UnsupportedOperationException("POST not implemented in test mock")
    }
}

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    // Use our serializable HttpClient
    private lateinit var httpClient: SerializableHttpClient
    
    // Test instances
    private lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    private lateinit var fetcherFnMinute: TiingoCryptoFetcherFn
    
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
        // Create serializable HTTP client
        httpClient = SerializableHttpClient()
        
        // Create fetcher functions
        fetcherFnDaily = TiingoCryptoFetcherFn(httpClient, Duration.standardDays(1), testApiKey)
        fetcherFnMinute = TiingoCryptoFetcherFn(httpClient, Duration.standardMinutes(1), testApiKey)
    }
    
    @Test
    fun `initial fetch uses default start date`() {
        val currencyPair = "BTC/USD"
        
        // Configure HTTP client response for default start date
        httpClient.setResponse("startDate=2019-01-02", sampleResponseDailyPage1)
        
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
        
        // Configure HTTP client to return empty response
        httpClient.setResponse("startDate=2019-01-02", emptyResponse)
        
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
        
        // Create a HTTP client with two different responses for the two fetch calls
        val testHttpClient = SerializableHttpClient()
        testHttpClient.setResponse("startDate=2019-01-02", sampleResponseDailyPage1)
        testHttpClient.setResponse("startDate=2023-10-28", sampleResponseDailyPage2)
        
        // Create the fetcherFn with our test HTTP client
        val fetcherFn = TiingoCryptoFetcherFn(testHttpClient, Duration.standardDays(1), testApiKey)
        
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
        
        // Create fetcherFn with invalid API key
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(httpClient, Duration.standardDays(1), "")
        
        // Setup pipeline
        val input = pipeline.apply(Create.of(KV.of(currencyPair, null as Void?)))
        val output = input.apply(ParDo.of(fetcherFnInvalidKey))
        
        // Verify no output
        PAssert.that(output).empty()
        
        pipeline.run()
    }
    
    @Test
    fun `handle http error gracefully`() {
        val currencyPair = "BTC/USD"
        
        // Configure HTTP client to throw exception
        httpClient.setException("", IOException("Network Error"))
        
        // Setup pipeline
        val input = pipeline.apply(Create.of(KV.of(currencyPair, null as Void?)))
        val output = input.apply(ParDo.of(fetcherFnDaily))
        
        // Verify no output
        PAssert.that(output).empty()
        
        pipeline.run()
    }
}
