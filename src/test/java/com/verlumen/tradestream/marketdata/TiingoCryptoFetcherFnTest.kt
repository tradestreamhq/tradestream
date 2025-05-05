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
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Rule
import org.junit.Test
import java.io.Serializable
import java.io.IOException

class TiingoCryptoFetcherFnTest {

  @get:Rule
  val pipeline: TestPipeline = TestPipeline.create()

  private val testApiKey = "TEST_API_KEY_123"
  private val emptyResponse = "[]"

  // two‐page sample for daily candles
  private val sampleResponseDailyPage1 = """
    [{"ticker":"btcusd","priceData":[
      {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
      {"date":"2023-10-27T00:00:00+00:00","open":34650,"high":35000,"low":34500,"close":34950,"volume":1800}
    ]}]
  """.trimIndent()

  private val sampleResponseDailyPage2 = """
    [{"ticker":"btcusd","priceData":[
      {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
    ]}]
  """.trimIndent()

  // a simple serializable stub
  private class StubHttpClient(
    private val responses: MutableList<String>
  ) : HttpClient, Serializable {
    override fun get(url: String, headers: Map<String, String>): String =
      if (responses.isNotEmpty()) responses.removeAt(0) else "[]"
  }

  @Test
  fun `initial fetch outputs expected candles`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyPage1))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val input: PCollection<KV<String, Void?>> =
      pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
    val output = input.apply(ParDo.of(fn))

    PAssert.that(output).satisfies { results: Iterable<KV<String, Candle>> ->
      val closes = results.map { it.value.close }
      assertThat(closes).containsExactly(34650.0, 34950.0)
      null
    }

    pipeline.run()
  }

  @Test
  fun `initial fetch with empty response produces no output`() {
    val stub = StubHttpClient(mutableListOf(emptyResponse))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val input: PCollection<KV<String, Void?>> =
      pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
    val output = input.apply(ParDo.of(fn))

    PAssert.that(output).empty()
    pipeline.run()
  }

  @Test
  fun `skip fetch if api key is invalid`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyPage1))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), "")

    val input: PCollection<KV<String, Void?>> =
      pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
    val output = input.apply(ParDo.of(fn))

    PAssert.that(output).empty()
    pipeline.run()
  }

  @Test
  fun `handle http error gracefully`() {
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        throw IOException("Network Error")
      }
    }
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val input: PCollection<KV<String, Void?>> =
      pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
    val output = input.apply(ParDo.of(fn))

    PAssert.that(output).empty()
    pipeline.run()
  }

  @Test
  fun `stateful incremental fetching with TestStream`() {
    val stub = StubHttpClient(
      mutableListOf(sampleResponseDailyPage1, sampleResponseDailyPage2)
    )
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val stream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), VoidCoder.of()))
      .addElements(
        TimestampedValue.of(KV.of("BTC/USD", null as Void?), Instant(0L))
      )
      .advanceProcessingTime(Duration.standardHours(1))
      .addElements(
        TimestampedValue.of(KV.of("BTC/USD", null as Void?), Instant(3_600_000L))
      )
      .advanceWatermarkToInfinity()

    val input: PCollection<KV<String, Void?>> = pipeline.apply(stream)
    val output = input.apply(ParDo.of(fn))

    PAssert.that(output).satisfies { results: Iterable<KV<String, Candle>> ->
      val closes = results.map { it.value.close }.toSet()
      assertThat(closes).containsExactly(34650.0, 34950.0, 35100.0)
      null
    }

    pipeline.run()
  }
}
