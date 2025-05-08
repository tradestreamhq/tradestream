package com.verlumen.tradestream.marketdata

import com.verlumen.tradestream.http.HttpClient
import com.google.common.truth.Truth.assertThat
import com.google.protobuf.util.Timestamps
import com.google.protobuf.Timestamp
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.coders.VoidCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant as JodaInstant
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.IOException
import java.io.Serializable

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

  @get:Rule
  val pipeline: TestPipeline = TestPipeline.create()

  private val testApiKey = "TEST_API_KEY_123"
  private val emptyResponse = "[]"

  // two‐page sample for daily candles
  private val sampleResponseDailyPage1 = """
    [{"ticker":"btcusd","priceData":[
      {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
      {"date":"2023-10-27T00:00:00+00:00","open":34700,"high":35000,"low":34600,"close":34900,"volume":1600}
    ]}]
  """.trimIndent()

  private val sampleResponseDailyPage2 = """
    [{"ticker":"btcusd","priceData":[
      {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
    ]}]
  """.trimIndent()

  // Sample response with a one‐day gap
  private val sampleResponseDailyWithGap = """
    [{"ticker":"btcusd","priceData":[
      {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
      {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
    ]}]
  """.trimIndent()

  // Sample minute response with a gap
  private val sampleResponseMinuteWithGap = """
    [{"ticker":"ethusd","priceData":[
      {"date":"2023-10-27T10:01:00+00:00","open":2000,"high":2002,"low":1999,"close":2001,"volume":5.2},
      {"date":"2023-10-27T10:03:00+00:00","open":2003,"high":2005,"low":2000,"close":2004,"volume":6.1}
    ]}]
  """.trimIndent()

  private class StubHttpClient(
    private val responses: MutableList<String>
  ) : HttpClient, Serializable {
    private val usedUrls = mutableListOf<String>()
    override fun get(url: String, headers: Map<String, String>): String {
      usedUrls.add(url)
      return if (responses.isNotEmpty()) responses.removeAt(0) else "[]"
    }
    fun getUsedUrls(): List<String> = usedUrls
  }

  @Test
  fun `fetcher passes correct URL parameters`() {
    val stub = StubHttpClient(mutableListOf(emptyResponse))
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    // run through a single Create to invoke processElement once
    pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply(ParDo.of(fn))
    pipeline.run()

    val urls = stub.getUsedUrls()
    assertThat(urls).hasSize(1)
    assertThat(urls[0]).contains("tickers=btcusd")
    assertThat(urls[0]).contains("resampleFreq=1day")
    assertThat(urls[0]).contains("token=$testApiKey")
  }

  @Test
  fun `initial fetch outputs expected daily candles`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyPage1))
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val result = pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply(ParDo.of(fn))

    PAssert.that(result).satisfies { iter ->
      val list = iter.map { it.value }.toList()
      assertThat(list).hasSize(2)
      assertThat(list[0].open).isEqualTo(34500.0)
      assertThat(list[1].close).isEqualTo(34900.0)
      null
    }
    pipeline.run()
  }

  @Test
  fun `fetcher handles empty response`() {
    val stub = StubHttpClient(mutableListOf(emptyResponse))
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val result = pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply(ParDo.of(fn))

    PAssert.that(result).empty()
    pipeline.run()
  }

  @Test
  fun `fillForward skips gaps on first fetch (daily)`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyWithGap))
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val result = pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply(ParDo.of(fn))

    PAssert.that(result).satisfies { iter ->
      val list = iter.map { it.value }.toList()
      // Only exactly the two fetched days, no synthetic in between
      assertThat(list).hasSize(2)
      assertThat(Timestamps.toMillis(list[0].timestamp))
        .isEqualTo(Instant.parse("2023-10-26T00:00:00Z").toEpochMilli())
      assertThat(Timestamps.toMillis(list[1].timestamp))
        .isEqualTo(Instant.parse("2023-10-28T00:00:00Z").toEpochMilli())
      null
    }
    pipeline.run()
  }

  @Test
  fun `fillForward skips gaps on first fetch (minute) with TestStream`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseMinuteWithGap))
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardMinutes(1),
        testApiKey
    )

    val stream = TestStream.create(
        KvCoder.of(StringUtf8Coder.of(), VoidCoder.of())
    )
    .addElements(
      TimestampedValue.of(KV.of("ETH/USD", null as Void?), JodaInstant(0L))
    )
    .advanceWatermarkToInfinity()

    val result = pipeline
      .apply(stream)
      .apply(ParDo.of(fn))

    PAssert.that(result).satisfies { iter ->
      val list = iter.map { it.value }.toList()
      // Only the two actual fetched, no synthetic at 10:02
      assertThat(list).hasSize(2)
      null
    }
    pipeline.run()
  }

  @Test
  fun `fetcher handles incremental processing`() {
    val stub = StubHttpClient(
      mutableListOf(sampleResponseDailyPage1, sampleResponseDailyPage2)
    )
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val stream = TestStream.create(
        KvCoder.of(StringUtf8Coder.of(), VoidCoder.of())
    )
    .addElements(
      TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(0L))
    )
    .advanceProcessingTime(Duration.standardHours(1))
    .addElements(
      TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(3_600_000L))
    )
    .advanceWatermarkToInfinity()

    val result = pipeline
      .apply(stream)
      .apply(ParDo.of(fn))

    PAssert.that(result).satisfies { iter ->
      val list = iter.map { it.value }.toList()
      // 2 from page1 + 1 from page2 = 3 total
      assertThat(list).hasSize(3)
      null
    }
    pipeline.run()
  }
}
