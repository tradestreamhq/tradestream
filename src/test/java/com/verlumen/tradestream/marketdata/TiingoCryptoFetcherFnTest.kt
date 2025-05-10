package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.util.Timestamps
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
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant as JodaInstant
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.Serializable
import java.time.Instant
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest : Serializable {
  // Making class serializable
  private val serialVersionUID = 1L

  @get:Rule
  @Transient
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
  
  // Reusable HTTP client classes
  class SimpleHttpClient(private val response: String) : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String = response
  }
  
  class UrlCapturingHttpClient(private val response: String, private val urls: MutableList<String>) : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
          urls.add(url)
          return response
      }
  }
  
  class SequentialHttpClient(private val responses: List<String>) : HttpClient, Serializable {
      private val index = AtomicInteger(0)
      val capturedUrls = CopyOnWriteArrayList<String>()
      
      override fun get(url: String, headers: Map<String, String>): String {
          capturedUrls.add(url)
          val currentIndex = index.getAndIncrement() % responses.size
          return responses[currentIndex]
      }
  }

  @Test
  fun `fetcher passes correct URL parameters`() {
    // For this test, we need to ensure the URL is captured
    // Use an atomic reference that will survive the DoFn serialization
    val httpClientWithCapturedUrl = object : HttpClient, Serializable {
      // Explicitly store the url in a thread-safe way
      val url = java.util.concurrent.atomic.AtomicReference<String>()
      
      override fun get(url: String, headers: Map<String, String>): String {
        this.url.set(url)
        return sampleResponseDailyPage1
      }
    }
    
    val fn = TiingoCryptoFetcherFn(
        httpClientWithCapturedUrl,
        Duration.standardDays(1),
        testApiKey
    )

    pipeline
      .apply(Create.of(KV.of("BTC/USD", null as Void?)))
      .apply("Fetch", ParDo.of(fn))

    pipeline.run().waitUntilFinish()

    // After pipeline completes, verify the URL
    val capturedUrl = httpClientWithCapturedUrl.url.get()
    assertThat(capturedUrl).isNotNull()
    assertThat(capturedUrl).contains("tickers=btcusd")
    assertThat(capturedUrl).contains("resampleFreq=1day")
    assertThat(capturedUrl).contains("token=$testApiKey")
    
    // Check that startDate is present and formatted correctly (YYYY-MM-DD)
    assertThat(capturedUrl).containsMatch("startDate=\\d{4}-\\d{2}-\\d{2}")
  }

  @Test
  fun `initial fetch outputs expected daily candles`() {
    // Simple serializable HTTP client
    val stub = SimpleHttpClient(sampleResponseDailyPage1)
    
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
    // Simple serializable HTTP client
    val stub = SimpleHttpClient(emptyResponse)
    
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
    // Simple serializable HTTP client
    val stub = SimpleHttpClient(sampleResponseDailyWithGap)
    
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
    // Simple serializable HTTP client
    val stub = SimpleHttpClient(sampleResponseMinuteWithGap)
    
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
    // For this test, we need a stable client that returns predictable responses
    val httpClient = object : HttpClient, Serializable {
      // Use a transient array to hold the responses (will be reset after deserialization)
      @Transient private var responses = arrayOf(sampleResponseDailyPage1, sampleResponseDailyPage2)
      @Transient private var indexCounter = 0
      
      // We need a thread-safe way to track URLs
      val capturedUrls = CopyOnWriteArrayList<String>()
      
      override fun get(url: String, headers: Map<String, String>): String {
        capturedUrls.add(url)
        // Always return first response on first call, second response on second call
        return if (indexCounter == 0) {
          indexCounter++
          sampleResponseDailyPage1
        } else {
          sampleResponseDailyPage2
        }
      }
    }
    
    val fn = TiingoCryptoFetcherFn(
        httpClient,
        Duration.standardDays(1),
        testApiKey
    )

    // Create a TestStream with two triggers
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

    // Apply to pipeline and get results
    val result = pipeline
        .apply(stream)
        .apply("FetchCandles", ParDo.of(fn))

    // Verify with PAssert
    val day1 = createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)
    val day2 = createExpectedCandle("BTC/USD", "2023-10-27T00:00:00+00:00", 34700.0, 35000.0, 34600.0, 34900.0, 1600.0) 
    val day3 = createExpectedCandle("BTC/USD", "2023-10-28T00:00:00+00:00", 34950.0, 35200.0, 34800.0, 35100.0, 1200.0)
    
    PAssert.that(result).containsInAnyOrder(
        KV.of("BTC/USD", day1),
        KV.of("BTC/USD", day2),
        KV.of("BTC/USD", day3)
    )
    
    pipeline.run().waitUntilFinish()
    
    // Verify URLs were captured (at least 2)
    assertThat(httpClient.capturedUrls).hasSize(2)
    
    // The second URL should request data starting after Oct 27 (the last day in the first response)
    val expectedStartDateFormatted = "2023-10-28"
    assertThat(httpClient.capturedUrls[1]).contains("startDate=$expectedStartDateFormatted")
  }
  
  @Test
  fun `fetcher respects max fill forward limit`() {
    // For this test, we'll do a simpler approach without trying to capture outputs directly
    val initialResponse = """
      [{"ticker":"btcusd","priceData":[
        {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500}
      ]}]
    """.trimIndent()
    
    val emptyFollowUpResponse = "[]"
    
    // Create a sequential client to return an initial response then empty
    val client = SequentialHttpClient(listOf(initialResponse, emptyFollowUpResponse))
    
    val fn = TiingoCryptoFetcherFn(
        client,
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
    
    val result = pipeline
        .apply(stream)
        .apply("FetchWithFillLimit", ParDo.of(fn))
    
    // We can't easily count the exact output elements, but we can verify that the
    // output collection is not empty and contains valid candles
    PAssert.that(result).satisfies { output ->
        val candles = output.toList()
        
        // Should at least have the original Oct 26 candle
        val hasOct26 = candles.any { 
            it.key == "BTC/USD" && 
            Instant.ofEpochSecond(it.value.timestamp.seconds).toString().contains("2023-10-26")
        }
        
        assertThat(hasOct26).isTrue()
        
        // We should have some candles but not hundreds - proving fill-forward is limited
        // Check that we don't have any candles from today
        val now = java.time.LocalDate.now()
        val hasCurrentDay = candles.any {
            val candleDate = Instant.ofEpochSecond(it.value.timestamp.seconds)
                .atZone(ZoneOffset.UTC).toLocalDate()
            candleDate.isEqual(now)
        }
        
        // We should NOT have candles from today
        assertThat(hasCurrentDay).isFalse()
        
        null as Void? // Return expected Void? type
    }
    
    pipeline.run()
  }
}
