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
import org.apache.beam.sdk.values.PCollection
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
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicReference

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

  @get:Rule
  @Transient // Add transient modifier
  val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

  private val testApiKey = "TEST_API_KEY_123"
  private val emptyResponse = "[]"

  // Sample for daily candles
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

  // Sample response with a one-day gap
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

  // Use a thread-safe, serializable stub with better URL tracking
  private class StubHttpClient : HttpClient, Serializable {
    @Transient private val responseQueue: ConcurrentLinkedQueue<String>
    @Transient private val usedUrls: CopyOnWriteArrayList<String>

    constructor(initialResponses: List<String>) {
      responseQueue = ConcurrentLinkedQueue(initialResponses)
      usedUrls = CopyOnWriteArrayList()
    }
    
    // Additional constructor that takes a shared reference to track URLs across serialization
    constructor(initialResponses: List<String>, urlsRef: AtomicReference<MutableList<String>>) {
      responseQueue = ConcurrentLinkedQueue(initialResponses)
      usedUrls = CopyOnWriteArrayList()
      this.urlsRef = urlsRef
    }
    
    @Transient private var urlsRef: AtomicReference<MutableList<String>>? = null

    override fun get(url: String, headers: Map<String, String>): String {
      usedUrls.add(url)
      // Also add to the shared reference if available
      urlsRef?.get()?.add(url)
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
      responseQueue = ConcurrentLinkedQueue(restoredResponses)
      usedUrls = CopyOnWriteArrayList(restoredUrls)
    }

    companion object {
       private const val serialVersionUID: Long = 3L
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
  fun `fetcher passes correct URL parameters`() {
    // Use AtomicReference to track URLs across serialization
    val urlsRef = AtomicReference<MutableList<String>>(mutableListOf())
    
    val responses = mutableListOf(sampleResponseDailyPage1)
    val stub = StubHttpClient(responses, urlsRef)
    
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply("Fetch", ParDo.of(fn))

    pipeline.run().waitUntilFinish()

    // Assert URL parameters after pipeline runs
    val urls = urlsRef.get()
    assertThat(urls).hasSize(1)
    assertThat(urls[0]).contains("tickers=btcusd")
    assertThat(urls[0]).contains("resampleFreq=1day")
    assertThat(urls[0]).contains("token=$testApiKey")
    assertThat(urls[0]).contains("startDate=2019-01-02")
  }

  @Test
  fun `initial fetch outputs expected daily candles`() {
    val responses = mutableListOf(sampleResponseDailyPage1)
    val stub = StubHttpClient(responses)
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
  fun `fetcher handles empty response`() {
    val responses = mutableListOf(emptyResponse)
    val stub = StubHttpClient(responses)
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
    val stub = StubHttpClient(responses)
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
    val stub = StubHttpClient(responses)
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
  fun `fetcher handles incremental processing`() {
    // For this test, we'll separate the setup of each trigger
    // and verify the output separately
    
    // Create a TestStream with two separate element triggers
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

    // Create the stub with appropriate responses for each trigger
    val responses = listOf(sampleResponseDailyPage1, sampleResponseDailyPage2)
    val stub = StubHttpClient(responses)
    
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )

    // Create our test pipeline with the stream and transform
    val testOutput: PCollection<KV<String, Candle>> = pipeline
        .apply(stream)
        .apply("FetchCandles", ParDo.of(fn))

    // Check output includes all three expected candles
    PAssert.that(testOutput).satisfies { output ->
      val outputList = output.toList()
      
      // Verify we have 3 candles in total
      assertThat(outputList).hasSize(3)
      
      // Check for all 3 expected candles
      val day1 = createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)
      val day2 = createExpectedCandle("BTC/USD", "2023-10-27T00:00:00+00:00", 34700.0, 35000.0, 34600.0, 34900.0, 1600.0)
      val day3 = createExpectedCandle("BTC/USD", "2023-10-28T00:00:00+00:00", 34950.0, 35200.0, 34800.0, 35100.0, 1200.0)
      
      // Make sure each day is in the output
      val hasDay1 = outputList.any { 
        it.key == "BTC/USD" && it.value.timestamp.seconds == day1.timestamp.seconds 
      }
      val hasDay2 = outputList.any { 
        it.key == "BTC/USD" && it.value.timestamp.seconds == day2.timestamp.seconds 
      }
      val hasDay3 = outputList.any { 
        it.key == "BTC/USD" && it.value.timestamp.seconds == day3.timestamp.seconds 
      }
      
      assertThat(hasDay1).isTrue()
      assertThat(hasDay2).isTrue()
      assertThat(hasDay3).isTrue()
      
      return null
    }
    
    pipeline.run()
    
    // Also check URLs used
    val urls = stub.getUsedUrls()
    assertThat(urls).hasSize(2)
    assertThat(urls[0]).contains("startDate=2019-01-02") // Initial fetch
    
    // The second URL should request data starting after Oct 27 (the last day in the first response)
    val expectedStartDateFormatted = "2023-10-28"
    assertThat(urls[1]).contains("startDate=$expectedStartDateFormatted")
  }
  
  @Test
  fun `fetcher respects max fill forward limit`() {
    // Use a test that checks if fill-forward is limited properly
    val initialResponse = """
      [{"ticker":"btcusd","priceData":[
        {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500}
      ]}]
    """.trimIndent()
    
    val emptyFollowUpResponse = "[]" // Empty follow-up response should trigger limited fill-forward
    
    val responses = listOf(initialResponse, emptyFollowUpResponse)
    val stub = StubHttpClient(responses)
    
    val fn = TiingoCryptoFetcherFn(
        stub,
        Duration.standardDays(1),
        testApiKey
    )
    
    // Create a TestStream with two triggers spaced far apart
    val stream = TestStream.create(
        KvCoder.of(StringUtf8Coder.of(), VoidCoder.of())
    )
        .addElements(
            TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(0L))
        )
        .advanceProcessingTime(Duration.standardDays(7)) // Advance a week
        .addElements(
            TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(7 * 24 * 3_600_000L)) // A week later
        )
        .advanceWatermarkToInfinity()
    
    val testOutput = pipeline
        .apply(stream)
        .apply("FetchWithFillLimit", ParDo.of(fn))
    
    // Verify output doesn't have too many forward-filled candles
    PAssert.that(testOutput).satisfies { output ->
      val outputList = output.toList()
      
      // First, verify we have the original Oct 26 candle
      val hasOct26 = outputList.any {
        it.key == "BTC/USD" && 
        Instant.ofEpochSecond(it.value.timestamp.seconds).toString().contains("2023-10-26")
      }
      assertThat(hasOct26).isTrue()
      
      // Check that we don't have candles from the current day
      val now = java.time.LocalDate.now()
      val hasCurrentDay = outputList.any {
        val candleDate = Instant.ofEpochSecond(it.value.timestamp.seconds)
                            .atZone(ZoneOffset.UTC).toLocalDate()
        candleDate.isEqual(now)
      }
      
      // We should not have candles from today (the current day)
      assertThat(hasCurrentDay).isFalse()
      
      // The total number of candles should be reasonable (not excessive fill-forward)
      // For daily data, this should be a small number - much less than the days since Oct 26, 2023
      val daysBetween = java.time.temporal.ChronoUnit.DAYS.between(
          java.time.LocalDate.of(2023, 10, 26),
          java.time.LocalDate.now()
      )
      
      // We should have significantly fewer candles than the total days between
      // Oct 26, 2023 and now - this proves fill-forward is limited
      assertThat(outputList.size).isLessThan(daysBetween.toInt())
      
      return null
    }
    
    pipeline.run()
  }
}
