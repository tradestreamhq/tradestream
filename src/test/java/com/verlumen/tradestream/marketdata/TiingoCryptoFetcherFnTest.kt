package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder // Import ProtoCoder
import org.apache.beam.sdk.state.ValueState // Import ValueState
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
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
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.io.IOException
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Collections

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock
    lateinit var mockHttpClient: HttpClient

    // Test instances
    lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    lateinit var fetcherFnMinute: TiingoCryptoFetcherFn

    private val testApiKey = "TEST_API_KEY_123"

    // Sample responses remain the same...
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
        fetcherFnMinute = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardMinutes(1), testApiKey) // Use 1-min for testing
    }

    // --- Test Initial Fetch (No State) ---
    @Test
    fun `processElement initial fetch daily uses default start date`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1day", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseDailyPage1)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).hasSize(2) // Verify output
        val finalState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec) // Get state using spec
        assertThat(finalState).isNotNull()
        // State should be timestamp of the last candle in the batch
        assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(1698364800000L) // 2023-10-27T00:00:00Z
    }

     @Test
    fun `processElement initial fetch minute uses default start date`() {
        val currencyPair = "ETH/USD"
        val input = KV.of(currencyPair, null as Void?)
        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1min", "tickers=ethusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseMinutePage1)

        val tester = DoFnTester.of(fetcherFnMinute)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).hasSize(1) // Verify output
        val finalState: Timestamp? = tester.getState(fetcherFnMinute.lastTimestampSpec) // Get state using spec
        assertThat(finalState).isNotNull()
        assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(1698400860000L) // 2023-10-27T10:01:00Z
    }

     @Test
    fun `processElement initial fetch with empty response sets state to start date`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1day", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).isEmpty()
        val finalState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec)
        assertThat(finalState).isNotNull()
        // State should be the start of the DEFAULT_START_DATE
        val expectedStateDate = LocalDate.parse("2019-01-02")
        val expectedStateMillis = expectedStateDate.atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
        assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(expectedStateMillis)
    }


    // --- Test Subsequent Fetch (With State) ---
    @Test
    fun `processElement subsequent fetch daily uses correct next start date`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Arrange: Set initial state
        val initialTimestampMillis = 1698364800000L // 2023-10-27T00:00:00Z
        val initialTimestampProto = Timestamps.fromMillis(initialTimestampMillis)
        val tester = DoFnTester.of(fetcherFnDaily)
        tester.setState(fetcherFnDaily.lastTimestampSpec, initialTimestampProto) // Set initial state

        // Mock HTTP client for the *next* day's fetch
        val expectedStartDate = "2023-10-28" // Day after state
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1day", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseDailyPage2)

        // Act
        val outputs = tester.processBundle(listOf(input))

        // Assert
        assertThat(outputs).hasSize(1)
        assertThat(outputs[0].value.close).isEqualTo(35100.0)
        val finalState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec)
        assertThat(finalState).isNotNull()
        // State should be updated to the new latest candle
        assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(1698451200000L) // 2023-10-28T00:00:00Z
    }

    @Test
    fun `processElement subsequent fetch minute uses correct next start time`() {
        val currencyPair = "ETH/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Arrange: Set initial state
        val initialTimestampMillis = 1698400860000L // 2023-10-27T10:01:00Z
        val initialTimestampProto = Timestamps.fromMillis(initialTimestampMillis)
        val tester = DoFnTester.of(fetcherFnMinute)
        tester.setState(fetcherFnMinute.lastTimestampSpec, initialTimestampProto)

        // Mock HTTP client for the *next* second's fetch
        val expectedStartTime = "2023-10-27T10:01:01" // Second after state
        val urlMatcher = UrlMatcher("startDate=$expectedStartTime", "resampleFreq=1min", "tickers=ethusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseMinutePage2)

        // Act
        val outputs = tester.processBundle(listOf(input))

        // Assert
        assertThat(outputs).hasSize(1)
        assertThat(outputs[0].value.close).isEqualTo(2004.0)
        val finalState: Timestamp? = tester.getState(fetcherFnMinute.lastTimestampSpec)
        assertThat(finalState).isNotNull()
        assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(1698400920000L) // 2023-10-27T10:02:00Z
    }

     @Test
    fun `processElement subsequent fetch with empty response leaves state unchanged`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Arrange: Set initial state
        val initialTimestampMillis = 1698364800000L // 2023-10-27T00:00:00Z
        val initialTimestampProto = Timestamps.fromMillis(initialTimestampMillis)
        val tester = DoFnTester.of(fetcherFnDaily)
        tester.setState(fetcherFnDaily.lastTimestampSpec, initialTimestampProto)

        // Mock HTTP client to return empty
        val expectedStartDate = "2023-10-28"
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1day", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(emptyResponse)

        // Act
        val outputs = tester.processBundle(listOf(input))

        // Assert
        assertThat(outputs).isEmpty()
        val finalState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec)
        // State should NOT have been updated
        assertThat(finalState).isEqualTo(initialTimestampProto)
    }


    // --- Other Tests (remain the same) ---
    @Test
    fun `processElement skips fetch if api key is invalid`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)
        val fetcherFnInvalidKey = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "") // Empty Key

        val tester = DoFnTester.of(fetcherFnInvalidKey)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).isNotNull()
        assertThat(outputs).isEmpty()
        Mockito.verify(mockHttpClient, Mockito.never()).get(Mockito.anyString(), Mockito.anyMap())
    }

    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void?> = KV.of(currencyPair, null)

        val urlMatcher = UrlMatcher("token=$testApiKey")
         Mockito.`when`(mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) }, Mockito.anyMap()))
            .thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).isNotNull()
        assertThat(outputs).isEmpty()
        // Verify state didn't change (it shouldn't exist yet)
        val finalState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec)
        assertThat(finalState).isNull()
    }

    // --- Mockito ArgumentMatcher Implementation ---
    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean {
            return argument != null && substrings.all { argument.contains(it) }
        }
        override fun toString(): String = "URL containing $substrings"
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
