package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
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
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant as JodaInstant
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.Serializable
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

  @get:Rule
  @field:Transient // Add transient modifier
  val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false) // Disable abandoned node enforcement for stateful tests

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

  // Use a thread-safe, serializable stub
  private class StubHttpClient(initialResponses: List<String>) : HttpClient, Serializable {
    // Use transient to avoid serializing non-serializable collections directly
    @Transient private var responseQueue: java.util.concurrent.ConcurrentLinkedQueue<String> = java.util.concurrent.ConcurrentLinkedQueue(initialResponses)
    @Transient private var usedUrls: java.util.concurrent.CopyOnWriteArrayList<String> = java.util.concurrent.CopyOnWriteArrayList()

    override fun get(url: String, headers: Map<String, String>): String {
      usedUrls.add(url)
      return responseQueue.poll() ?: "[]" // Return empty array if queue is empty
    }

    fun getUsedUrls(): List<String> = usedUrls.toList()

    @Throws(java.io.IOException::class)
    private fun writeObject(out: java.io.ObjectOutputStream) {
        out.defaultWriteObject()
        // Write the *contents* of the collections
        out.writeObject(ArrayList(responseQueue))
        out.writeObject(ArrayList(usedUrls))
    }

    @Suppress("UNCHECKED_CAST")
    @Throws(java.io.IOException::class, ClassNotFoundException::class)
    private fun readObject(ois: java.io.ObjectInputStream) {
        ois.defaultReadObject()
        // Read the contents back
        val restoredResponses = ois.readObject() as ArrayList<String>
        val restoredUrls = ois.readObject() as ArrayList<String>
        // Re-initialize the transient fields
        responseQueue = java.util.concurrent.ConcurrentLinkedQueue(restoredResponses)
        usedUrls = java.util.concurrent.CopyOnWriteArrayList(restoredUrls)
    }

    companion object {
         private const val serialVersionUID: Long = 2L // Incremented version
     }
  }


  // Helper to create expected Candle for assertions
  private fun createExpectedCandle(pair: String, tsStr: String, o: Double, h: Double, l: Double, c: Double, v: Double): Candle {
    // Ensure Z at the end for UTC parsing
    val instant = Instant.parse(tsStr.replace("+00:00", "Z"))
    val ts = Timestamps.fromMillis(instant.toEpochMilli())
      return Candle.newBuilder()
          .setTimestamp(ts).setCurrencyPair(pair)
          .setOpen(o).setHigh(h).setLow(l).setClose(c).setVolume(v)
          .build()
  }

  @Test
  fun `Workspaceer passes correct URL parameters`() {
    val responses = mutableListOf(sampleResponseDailyPage1)
    val stub = StubHttpClient(responses.toList())
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey // Pass the non-blank API key
    )

    pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply("Fetch", ParDo.of(fn))

    pipeline.run().waitUntilFinish()

    // Assert URL parameters after pipeline runs
    val urls = stub.getUsedUrls()
    assertThat(urls).hasSize(1) // Now this should pass
    assertThat(urls[0]).contains("tickers=btcusd")
    assertThat(urls[0]).contains("resampleFreq=1day")
    assertThat(urls[0]).contains("token=$testApiKey")
    assertThat(urls[0]).contains("startDate=2019-01-02")
  }

  @Test
  fun `initial fetch outputs expected daily candles`() {
    val responses = mutableListOf(sampleResponseDailyPage1)
    val stub = StubHttpClient(responses.toList())
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val result = pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply(ParDo.of(fn))

    // Assert on the output PCollection directly
    PAssert.that(result).containsInAnyOrder(
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)),
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-27T00:00:00+00:00", 34700.0, 35000.0, 34600.0, 34900.0, 1600.0))
    )
    pipeline.run()
  }

  @Test
  fun `Workspaceer handles empty response`() {
    val responses = mutableListOf(emptyResponse)
    val stub = StubHttpClient(responses.toList())
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
    val responses = mutableListOf(sampleResponseDailyWithGap)
    val stub = StubHttpClient(responses.toList())
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val result = pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply(ParDo.of(fn))

    // Expecting only the two real candles, no fill-forward on initial fetch
    PAssert.that(result).containsInAnyOrder(
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)),
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-28T00:00:00+00:00", 34950.0, 35200.0, 34800.0, 35100.0, 1200.0))
    )
    pipeline.run()
  }

  @Test
  fun `fillForward skips gaps on first fetch (minute) with TestStream`() {
    val responses = mutableListOf(sampleResponseMinuteWithGap)
    val stub = StubHttpClient(responses.toList())
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardMinutes(1),
        testApiKey
    )

    val stream = TestStream.create(
        KvCoder.of(StringUtf8Coder.of(), VoidCoder.of())
    )
        .addElements( // First trigger
            TimestampedValue.of(KV.of("ETH/USD", null as Void?), JodaInstant(0L))
        )
        .advanceWatermarkToInfinity()

    val result = pipeline
      .apply(stream)
      .apply(ParDo.of(fn))

    // Expecting only the two real candles, no fill-forward on initial fetch
    PAssert.that(result).containsInAnyOrder(
        KV.of("ETH/USD", createExpectedCandle("ETH/USD", "2023-10-27T10:01:00+00:00", 2000.0, 2002.0, 1999.0, 2001.0, 5.2)),
        KV.of("ETH/USD", createExpectedCandle("ETH/USD", "2023-10-27T10:03:00+00:00", 2003.0, 2005.0, 2000.0, 2004.0, 6.1))
    )
    pipeline.run()
  }

  @Test
  fun `Workspaceer handles incremental processing`() {
     val responses = mutableListOf(sampleResponseDailyPage1, sampleResponseDailyPage2)
     val stub = StubHttpClient(responses.toList())
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    val stream = TestStream.create(
        KvCoder.of(StringUtf8Coder.of(), VoidCoder.of())
    )
        .addElements( // First trigger
            TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(0L))
        )
        .advanceProcessingTime(Duration.standardHours(1)) // Advance time between triggers
        .addElements( // Second trigger
            TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(3_600_000L))
        )
        .advanceWatermarkToInfinity()

    val result = pipeline
      .apply(stream)
      .apply(ParDo.of(fn))

    // Assert all 3 candles are emitted across both triggers
    PAssert.that(result).containsInAnyOrder(
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)),
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-27T00:00:00+00:00", 34700.0, 35000.0, 34600.0, 34900.0, 1600.0)),
        KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-28T00:00:00+00:00", 34950.0, 35200.0, 34800.0, 35100.0, 1200.0))
    )

    pipeline.run()

    // Also check URLs used
    val urls = stub.getUsedUrls()
    assertThat(urls).hasSize(2)
    assertThat(urls[0]).contains("startDate=2019-01-02") // Initial fetch
    // Check the *second* URL uses the correct start date
    val lastFetchedDay1 = LocalDate.ofInstant(Instant.parse("2023-10-27T00:00:00Z"), ZoneOffset.UTC)
    val expectedStartDate2 = lastFetchedDay1.plusDays(1).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"))
    assertThat(urls[1]).contains("startDate=$expectedStartDate2") // Incremental fetch (day after last fetched: Oct 27)
  }
}
