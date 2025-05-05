package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mockito
import java.io.IOException
import java.io.Serializable

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    private lateinit var mockHttpClient: HttpClient
    private lateinit var fetcherFnDaily: TiingoCryptoFetcherFn
    private val testApiKey = "TEST_API_KEY_123"

    // A small JSON snippet with two daily candles
    private val sampleResponseDaily = """
      [{"ticker":"btcusd","priceData":[
        {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
        {"date":"2023-10-27T00:00:00+00:00","open":34650,"high":35000,"low":34500,"close":34950,"volume":1800}
      ]}]
    """.trimIndent()

    @Before
    fun setUp() {
        // Create a serializable Mockito mock
        mockHttpClient = Mockito.mock(
            HttpClient::class.java,
            Mockito.withSettings().serializable()
        )

        fetcherFnDaily = TiingoCryptoFetcherFn(
            mockHttpClient,
            Duration.standardDays(1),
            testApiKey
        )
    }

    @Test
    fun dailyFetchOutputsExpectedCandles() {
        val pair = "BTC/USD"

        Mockito.`when`(mockHttpClient.get(Mockito.anyString(), Mockito.anyMap()))
            .thenReturn(sampleResponseDaily)

        val input = pipeline
            .apply(Create.of(KV.of(pair, null as Void?)))

        val fetcherTransformDaily: PTransform<in PCollection<KV<String, Void>>, PCollection<KV<String, Candle>>> = ParDo.of(fetcherFnDaily)
        val output: PCollection<KV<String, Candle>> = input.apply("RunFetcherDaily", fetcherTransformDaily)

        PAssert.that(output).satisfies { elements: Iterable<KV<String, Candle>> ->
            val results = elements.toList()
            assertThat(results).hasSize(2)
            assertThat(results[0].key).isEqualTo(pair)
            assertThat(results[0].value.close).isEqualTo(34650.0)
            assertThat(results[1].value.close).isEqualTo(34950.0)
            null
        }

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun ioExceptionYieldsNoOutput() {
        val pair = "BTC/USD"
        Mockito.`when`(mockHttpClient.get(Mockito.anyString(), Mockito.anyMap()))
            .thenThrow(IOException("network error"))

        val input = pipeline
            .apply(Create.of(KV.of(pair, null as Void?)))

        val fetcherTransformIOException: PTransform<in PCollection<KV<String, Void>>, PCollection<KV<String, Candle>>> = ParDo.of(fetcherFnDaily)
        val output: PCollection<KV<String, Candle>> = input.apply("RunFetcherIOException", fetcherTransformIOException)

        PAssert.that(output).empty()

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun invalidApiKeySkipsFetch() {
        val invalidFn = TiingoCryptoFetcherFn(mockHttpClient, Duration.standardDays(1), "")
        val pair = "BTC/USD"

        val input = pipeline.apply(Create.of(KV.of(pair, null as Void?)))
        val invalidFetcherTransform: PTransform<in PCollection<KV<String, Void>>, PCollection<KV<String, Candle>>> = ParDo.of(invalidFn)
        val output: PCollection<KV<String, Candle>> = input.apply("RunFetcherInvalidKey", invalidFetcherTransform)

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()

        Mockito.verify(mockHttpClient, Mockito.never())
            .get(Mockito.anyString(), Mockito.anyMap())
    }
}
