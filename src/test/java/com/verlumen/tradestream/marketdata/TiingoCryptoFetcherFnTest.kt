package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.testing.DoFnTester
import org.apache.beam.sdk.testing.TestPipeline
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
import org.mockito.kotlin.whenever
import java.io.IOException
import java.util.Collections

/**
 * Tests for the TiingoCryptoFetcherFn DoFn.
 */
@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock
    lateinit var mockHttpClient: HttpClient

    private lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    private lateinit var fetcherFnMinute: TiingoCryptoFetcherFn

    private val testApiKey = "TEST_API_KEY_123"

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
        fetcherFnDaily = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), testApiKey)
        fetcherFnMinute = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardMinutes(5), testApiKey)
    }

    @Test
    fun `daily fetch outputs expected candles`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void> = KV.of(currencyPair, null)

        val expectedStartDate = "2019-01-02"
        val urlMatcher = UrlMatcher(
            "startDate=$expectedStartDate",
            "resampleFreq=1day",
            "tickers=btcusd",
            "token=$testApiKey"
        )

        Mockito.`when`(
            mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) },
                               Mockito.anyMap())
        ).thenReturn(sampleResponseDaily)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs: List<KV<String, Candle>> = tester.processBundle(listOf(input))

        assertThat(outputs).hasSize(2)
        assertThat(outputs[0].key).isEqualTo(currencyPair)
        assertThat(outputs[0].value.close).isEqualTo(34650.0)
        assertThat(outputs[1].value.close).isEqualTo(34950.0)
    }

    @Test
    fun `minute fetch outputs a single candle`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void> = KV.of(currencyPair, null)

        val urlMatcher = UrlMatcher(
            "startDate=2019-01-02",
            "resampleFreq=5min",
            "tickers=btcusd",
            "token=$testApiKey"
        )

        Mockito.`when`(
            mockHttpClient.get(Mockito.argThat { arg: String? -> urlMatcher.matches(arg) },
                               Mockito.anyMap())
        ).thenReturn(sampleResponseMinute)

        val tester = DoFnTester.of(fetcherFnMinute)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).hasSize(1)
        assertThat(outputs[0].value.close).isEqualTo(34965.0)
    }

    @Test
    fun `empty response yields no output`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void> = KV.of(currencyPair, null)

        Mockito.`when`(
            mockHttpClient.get(Mockito.argThat { it!!.contains("token=$testApiKey") },
                               Mockito.anyMap())
        ).thenReturn(emptyResponse)

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).isEmpty()
    }

    @Test
    fun `invalid api key skips fetch`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void> = KV.of(currencyPair, null)
        val invalidFn = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "")

        val tester = DoFnTester.of(invalidFn)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).isEmpty()
        Mockito.verify(mockHttpClient, Mockito.never()).get(Mockito.anyString(), Mockito.anyMap())
    }

    @Test
    fun `io exception yields no output`() {
        val currencyPair = "BTC/USD"
        val input: KV<String, Void> = KV.of(currencyPair, null)

        Mockito.`when`(
            mockHttpClient.get(Mockito.argThat { it!!.contains("token=$testApiKey") },
                               Mockito.anyMap())
        ).thenThrow(IOException("network error"))

        val tester = DoFnTester.of(fetcherFnDaily)
        val outputs = tester.processBundle(listOf(input))

        assertThat(outputs).isEmpty()
    }

    private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
        override fun matches(argument: String?): Boolean =
            argument != null && substrings.all { argument.contains(it) }
        override fun toString(): String = "URL containing ${substrings.joinToString()}"
    }
}
