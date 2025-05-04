package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.common.truth.Truth.assertThat
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.coders.VoidCoder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.DoFnTester
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.Values
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.io.IOException
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @get:Rule
    @JvmField
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Mock
    @Bind // Use Guice binding for the mock
    lateinit var mockHttpClient: HttpClient

    @Inject // Inject the DoFn with mocked dependencies
    lateinit var fetcherFn: TiingoCryptoFetcherFn

    // Sample responses
    private val sampleResponsePage1 = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-26T00:00:00+00:00", "open": 34500, "high": 34800, "low": 34200, "close": 34650, "volume": 1500},
         {"date": "2023-10-27T00:00:00+00:00", "open": 34650, "high": 35000, "low": 34500, "close": 34950, "volume": 1800}
       ]}]
    """.trimIndent()

    private val sampleResponsePage2 = """
       [{"ticker": "btcusd", "priceData": [
         {"date": "2023-10-28T00:00:00+00:00", "open": 34950, "high": 35200, "low": 34800, "close": 35100, "volume": 1200}
       ]}]
    """.trimIndent()

    private val emptyResponse = "[]"


    @Before
    fun setUp() {
        // Setup Guice injector
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this)
    }

    @Test
    fun `processElement initial fetch returns candles and updates state`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Mock HTTP client for initial fetch
        val expectedStartDate = "2019-01-02"
        val expectedUrl = contains("startDate=$expectedStartDate") and contains("tickers=btcusd")
        whenever(mockHttpClient.get(argThat(expectedUrl), any())).thenReturn(sampleResponsePage1)

        // Use DoFnTester for stateful testing
        val tester = DoFnTester.of(fetcherFn)

        // --- Act ---
        val outputCandles = tester.processBundle(input)

        // --- Assert ---
        // Check output candles
        assertThat(outputCandles).hasSize(2)
        assertThat(outputCandles.map { it.close }).containsExactly(34650.0, 34950.0).inOrder()

        // Check final state
        val finalState: Timestamp? = tester.getState(fetcherFn.lastTimestampSpec)
        assertThat(finalState).isNotNull()
        // Timestamp of the *last* candle from page 1
        assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(1698364800000L) // 2023-10-27
    }


    @Test
    fun `processElement subsequent fetch uses state for start date`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // --- Arrange Initial State ---
        val initialTimestampMillis = 1698364800000L // 2023-10-27 00:00:00 UTC
        val initialTimestampProto = Timestamps.fromMillis(initialTimestampMillis)
        val tester = DoFnTester.of(fetcherFn)
        tester.setState(fetcherFn.lastTimestampSpec, initialTimestampProto)

        // Mock HTTP client for subsequent fetch (expecting start date 2023-10-28)
        val expectedStartDate = "2023-10-28"
        val expectedUrl = contains("startDate=$expectedStartDate") and contains("tickers=btcusd")
        whenever(mockHttpClient.get(argThat(expectedUrl), any())).thenReturn(sampleResponsePage2)


        // --- Act ---
        val outputCandles = tester.processBundle(input)


        // --- Assert ---
        assertThat(outputCandles).hasSize(1)
        assertThat(outputCandles[0].close).isEqualTo(35100.0)

        // Check final state updated to the latest candle
        val finalState: Timestamp? = tester.getState(fetcherFn.lastTimestampSpec)
        assertThat(finalState).isNotNull()
         assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(1698451200000L) // 2023-10-28
    }


     @Test
    fun `processElement handles empty response`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Mock HTTP client to return empty response
        whenever(mockHttpClient.get(any(), any())).thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFn)
        val outputCandles = tester.processBundle(input)

        assertThat(outputCandles).isEmpty()
        // State should be updated to the queried start date if it was null before
         val finalState: Timestamp? = tester.getState(fetcherFn.lastTimestampSpec)
         assertThat(finalState).isNotNull()
         val expectedStateDate = LocalDate.parse("2019-01-02", DateTimeFormatter.ISO_LOCAL_DATE)
         val expectedStateMillis = expectedStateDate.atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli()
         assertThat(Timestamps.toMillis(finalState!!)).isEqualTo(expectedStateMillis)
    }

    @Test
    fun `processElement handles http error`() {
        val currencyPair = "BTC/USD"
        val input = KV.of(currencyPair, null as Void?)

        // Mock HTTP client to throw exception
        whenever(mockHttpClient.get(any(), any())).thenThrow(IOException("Network Error"))

        val tester = DoFnTester.of(fetcherFn)
        val outputCandles = tester.processBundle(input)

        assertThat(outputCandles).isEmpty()
         // State should remain unchanged
        val finalState: Timestamp? = tester.getState(fetcherFn.lastTimestampSpec)
        assertThat(finalState).isNull()

    }

    // Helper to create matchers for URL checks
    private fun contains(substring: String): (String) -> Boolean = { it.contains(substring) }
    private fun <T> argThat(matcher: (T) -> Boolean): T = org.mockito.kotlin.argThat(matcher)

}
