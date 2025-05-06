package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.DoFnTester
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
// Use java.time.Instant for easier comparison
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
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

    // Sample responses (combined page1 and page2 for easier testing of gaps)
     private val sampleResponseDailyCombined = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-26T00:00:00+00:00", "open": 34500, "high": 34800, "low": 34200, "close": 34650, "volume": 1500},
         // Missing 2023-10-27
         {"date": "2023-10-28T00:00:00+00:00", "open": 34950, "high": 35200, "low": 34800, "close": 35100, "volume": 1200}
       ]}]
    """.trimIndent()

     private val sampleResponseMinuteCombined = """
       [{"ticker": "ethusd", "priceData": [
         {"date": "2023-10-27T10:01:00+00:00", "open": 2000, "high": 2002, "low": 1999, "close": 2001, "volume": 5.2},
         // Missing 10:02
         {"date": "2023-10-27T10:03:00+00:00", "open": 2003, "high": 2005, "low": 2000, "close": 2004, "volume": 6.1}
       ]}]
    """.trimIndent()

    private val emptyResponse = "[]"


    @Before
    fun setUp() {
        fetcherFnDaily = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), testApiKey)
        fetcherFnMinute = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardMinutes(1), testApiKey)
    }

    // --- Previous Tests (Initial Fetch, Subsequent Fetch, Empty, Error) ---
    // These tests might need slight adjustments if their mocked responses are changed,
    // but their core logic testing state/initial fetch remains valid.
    // For brevity, only showing new / significantly modified tests.

    @Test
    fun `processElement initial fetch daily updates state correctly`() {
        // This test focuses only on the state update after a successful initial fetch
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)
        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1day", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseDailyPage1) // Use page 1 response

        val tester = DoFnTester.of(fetcherFnDaily)
        tester.processBundle(listOf(input)) // Run the process

        // Assert State
        val finalTimestampState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec)
        assertThat(finalTimestampState).isNotNull()
        // Should be the timestamp of the LAST candle in the response (2023-10-27)
        assertThat(Timestamps.toMillis(finalTimestampState!!)).isEqualTo(1698364800000L)

        val finalCandleState: Candle? = tester.getState(fetcherFnDaily.lastCandleSpec)
        assertThat(finalCandleState).isNotNull()
        assertThat(finalCandleState!!.close).isEqualTo(34950.0) // Close of the last candle
        assertThat(Timestamps.toMillis(finalCandleState.timestamp)).isEqualTo(1698364800000L)
    }


    // --- Fill Forward Tests ---

    @Test
    fun `processElement fill forward daily candles detects and fills gap`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Arrange: Set initial state to before the first candle in combined response
        val initialTimestampMillis = Instant.parse("2023-10-25T00:00:00Z").toEpochMilli()
        val initialTimestampProto = Timestamps.fromMillis(initialTimestampMillis)
        val initialCandle = Candle.newBuilder().setClose(34400.0).setTimestamp(initialTimestampProto).setCurrencyPair(currencyPair).build() // Example previous candle

        val tester = DoFnTester.of(fetcherFnDaily)
        tester.setState(fetcherFnDaily.lastTimestampSpec, initialTimestampProto)
        tester.setState(fetcherFnDaily.lastCandleSpec, initialCandle)

        // Mock response with a gap
        val expectedStartDate = "2023-10-26" // Day after state
        val urlMatcher = UrlMatcher("startDate=$expectedStartDate", "resampleFreq=1day", "tickers=btcusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseDailyCombined)

        // Act
        val outputKVs = tester.processBundle(listOf(input))

        // Assert Output
        assertThat(outputKVs).hasSize(3) // 2 real + 1 synthetic

        val timestamps = outputKVs.map { Timestamps.toMillis(it.value.timestamp) }
        val expectedTimestamps = listOf(
            Instant.parse("2023-10-26T00:00:00Z").toEpochMilli(),
            Instant.parse("2023-10-27T00:00:00Z").toEpochMilli(), // Filled
            Instant.parse("2023-10-28T00:00:00Z").toEpochMilli()
        )
        assertThat(timestamps).containsExactlyElementsIn(expectedTimestamps).inOrder()

        // Check the filled candle (index 1)
        val filledCandleKV = outputKVs[1]
        assertThat(filledCandleKV.key).isEqualTo(currencyPair)
        val filledCandle = filledCandleKV.value
        assertThat(filledCandle.volume).isEqualTo(0.0) // Zero volume
        assertThat(filledCandle.close).isEqualTo(34650.0) // Close of previous candle (2023-10-26)
        assertThat(filledCandle.open).isEqualTo(34650.0)
        assertThat(filledCandle.high).isEqualTo(34650.0)
        assertThat(filledCandle.low).isEqualTo(34650.0)
        assertThat(Timestamps.toMillis(filledCandle.timestamp)).isEqualTo(expectedTimestamps[1])

        // Assert State
        val finalTimestampState: Timestamp? = tester.getState(fetcherFnDaily.lastTimestampSpec)
        assertThat(finalTimestampState).isNotNull()
         // last *processed* timestamp state should be the last *real* candle (2023-10-28)
        assertThat(Timestamps.toMillis(finalTimestampState!!)).isEqualTo(expectedTimestamps[2])

        val finalCandleState: Candle? = tester.getState(fetcherFnDaily.lastCandleSpec)
        assertThat(finalCandleState).isNotNull()
        // last *emitted* candle state should be the last *real* candle (2023-10-28)
        assertThat(finalCandleState!!.close).isEqualTo(35100.0)
        assertThat(Timestamps.toMillis(finalCandleState.timestamp)).isEqualTo(expectedTimestamps[2])
    }

    @Test
    fun `processElement fill forward minute candles detects and fills gap`() {
        val currencyPair = "ETH/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Arrange: Set initial state to before the first candle
        val initialTimestampMillis = Instant.parse("2023-10-27T10:00:00Z").toEpochMilli()
        val initialTimestampProto = Timestamps.fromMillis(initialTimestampMillis)
         val initialCandle = Candle.newBuilder().setClose(1999.0).setTimestamp(initialTimestampProto).setCurrencyPair(currencyPair).build()

        val tester = DoFnTester.of(fetcherFnMinute)
        tester.setState(fetcherFnMinute.lastTimestampSpec, initialTimestampProto)
        tester.setState(fetcherFnMinute.lastCandleSpec, initialCandle)


        // Mock response with a gap
        val expectedStartTime = "2023-10-27T10:00:01"
        val urlMatcher = UrlMatcher("startDate=$expectedStartTime", "resampleFreq=1min", "tickers=ethusd")
        Mockito.`when`(mockHttpClient.get(argThat(urlMatcher), anyMap())).thenReturn(sampleResponseMinuteCombined)

        // Act
        val outputKVs = tester.processBundle(listOf(input))

        // Assert Output
        assertThat(outputKVs).hasSize(3) // 2 real + 1 synthetic

        val timestamps = outputKVs.map { Timestamps.toMillis(it.value.timestamp) }
        val expectedTimestamps = listOf(
            Instant.parse("2023-10-27T10:01:00Z").toEpochMilli(),
            Instant.parse("2023-10-27T10:02:00Z").toEpochMilli(), // Filled
            Instant.parse("2023-10-27T10:03:00Z").toEpochMilli()
        )
        assertThat(timestamps).containsExactlyElementsIn(expectedTimestamps).inOrder()

        // Check the filled candle (index 1)
        val filledCandle = outputKVs[1].value
        assertThat(filledCandle.volume).isEqualTo(0.0)
        assertThat(filledCandle.close).isEqualTo(2001.0) // Close of previous (10:01)
        assertThat(Timestamps.toMillis(filledCandle.timestamp)).isEqualTo(expectedTimestamps[1])

        // Assert State
        val finalTimestampState: Timestamp? = tester.getState(fetcherFnMinute.lastTimestampSpec)
        assertThat(finalTimestampState).isNotNull()
         // last *processed* timestamp state should be the last *real* candle (10:03)
        assertThat(Timestamps.toMillis(finalTimestampState!!)).isEqualTo(expectedTimestamps[2])

        val finalCandleState: Candle? = tester.getState(fetcherFnMinute.lastCandleSpec)
        assertThat(finalCandleState).isNotNull()
         // last *emitted* candle state should be the last *real* candle (10:03)
        assertThat(finalCandleState!!.close).isEqualTo(2004.0)
        assertThat(Timestamps.toMillis(finalCandleState.timestamp)).isEqualTo(expectedTimestamps[2])
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
