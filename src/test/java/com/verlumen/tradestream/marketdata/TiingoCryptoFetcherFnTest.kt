package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import java.io.IOException

/**
 * Tests for the TiingoCryptoFetcherFn DoFn.
 */
@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @get:Rule
    val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock
    private lateinit var mockHttpClient: HttpClient

    private lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    private val testApiKey = "TEST_API_KEY_123"

    private val sampleResponseDaily = """
        [{"ticker": "btcusd", "priceData": [
          {"date": "2023-10-26T00:00:00+00:00", "open": 34500, "high": 34800, "low": 34200, "close": 34650, "volume": 1500},
          {"date": "2023-10-27T00:00:00+00:00", "open": 34650, "high": 35000, "low": 34500, "close": 34950, "volume": 1800}
        ]}]
    """.trimIndent()

    @Before
    fun setUp() {
        fetcherFnDaily = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), testApiKey)
    }

    @Test
    fun dailyFetchOutputsExpectedCandles() {
        val currencyPair = "BTC/USD"

        Mockito.`when`(mockHttpClient.get(Mockito.anyString(), Mockito.anyMap()))
            .thenReturn(sampleResponseDaily)

        val output: PCollection<KV<String, Candle>> = pipeline
            .apply(Create.of(KV.of(currencyPair, null as Void?)))
            .apply(ParDo.of(fetcherFnDaily))

        PAssert.that(output).satisfies { candles ->
            val results = candles.toList()
            assertThat(results).hasSize(2)
            assertThat(results[0].key).isEqualTo(currencyPair)
            assertThat(results[0].value.close).isEqualTo(34650.0)
            assertThat(results[1].value.close).isEqualTo(34950.0)
            null
        }

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun ioExceptionYieldsNoOutput() {
        val currencyPair = "BTC/USD"

        Mockito.`when`(mockHttpClient.get(Mockito.anyString(), Mockito.anyMap()))
            .thenThrow(IOException("network error"))

        val output: PCollection<KV<String, Candle>> = pipeline
            .apply(Create.of(KV.of(currencyPair, null as Void?)))
            .apply(ParDo.of(fetcherFnDaily))

        PAssert.that(output).empty()

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun invalidApiKeySkipsFetch() {
        val invalidFn = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "")
        val currencyPair = "BTC/USD"

        val output: PCollection<KV<String, Candle>> = pipeline
            .apply(Create.of(KV.of(currencyPair, null as Void?)))
            .apply(ParDo.of(invalidFn))

        PAssert.that(output).empty()

        pipeline.run().waitUntilFinish()

        Mockito.verify(mockHttpClient, Mockito.never()).get(Mockito.anyString(), Mockito.anyMap())
    }
}
