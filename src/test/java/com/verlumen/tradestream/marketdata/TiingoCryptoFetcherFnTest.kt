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
import java.time.temporal.ChronoUnit
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CopyOnWriteArrayList

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest : Serializable {

  companion object {
    private const val serialVersionUID = 1L
  }

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

  @Test
  fun `fetcher passes correct URL parameters`() {
    // Create a concurrent list to collect URLs
    val collectedUrls = CopyOnWriteArrayList<String>()
    
    // Create a stub that explicitly adds to our collection
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        collectedUrls.add(url)
        return sampleResponseDailyPage1
      }
      
      private companion object {
         private const val serialVersionUID: Long = 4L
      }
    }
    
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
    assertThat(collectedUrls).isNotEmpty()
    val url = collectedUrls[0]
    assertThat(url).contains("tickers=btcusd")
    assertThat(url).contains("resampleFreq=1day")
    assertThat(url).contains("token=$testApiKey")
    
    // Check that startDate is present and formatted correctly (YYYY-MM-DD)
    assertThat(url).containsMatch("startDate=\\d{4}-\\d{2}-\\d{2}")
  }

  @Test
  fun `initial fetch outputs expected daily candles`() {
    // Simple serializable HTTP client
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        return sampleResponseDailyPage1
      }
      
      private companion object {
         private const val serialVersionUID: Long = 4L
      }
    }
    
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
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        return emptyResponse
      }
      
      private companion object {
         private const val serialVersionUID: Long = 4L
      }
    }
    
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
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        return sampleResponseDailyWithGap
      }
      
      private companion object {
         private const val serialVersionUID: Long = 4L
      }
    }
    
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
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        return sampleResponseMinuteWithGap
      }
      
      private companion object {
         private const val serialVersionUID: Long = 4L
      }
    }
    
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
    // For this test, we'll use a simpler approach
    val urlsCollector = CopyOnWriteArrayList<String>()
    val responseQueue = listOf(sampleResponseDailyPage1, sampleResponseDailyPage2)
    var responseIndex = 0
    
    // Simple serializable HTTP client
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        urlsCollector.add(url)
        val response = responseQueue[responseIndex]
        responseIndex++
        return response
      }
      
      private companion object {
         private const val serialVersionUID: Long = 5L
      }
    }
    
    val fn = TiingoCryptoFetcherFn(
        stub,
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
    
    // After the pipeline completes, verify the URLs
    assertThat(urlsCollector).hasSize(2)
    
    // The second URL should request data starting after Oct 27 (the last day in the first response)
    val expectedStartDateFormatted = "2023-10-28"
    assertThat(urlsCollector[1]).contains("startDate=$expectedStartDateFormatted")
  }
  
  @Test
  fun `fetcher respects max fill forward limit`() {
    // For this simpler test, we'll keep track of how many candles were emitted
    val initialResponse = """
      [{"ticker":"btcusd","priceData":[
        {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500}
      ]}]
    """.trimIndent()
    
    val emptyFollowUpResponse = "[]"
    
    val candles = mutableListOf<KV<String, Candle>>()
    var responseIndex = 0
    val responses = listOf(initialResponse, emptyFollowUpResponse)
    
    // Simple serializable HTTP client
    val stub = object : HttpClient, Serializable {
      override fun get(url: String, headers: Map<String, String>): String {
        val response = responses[responseIndex]
        responseIndex = (responseIndex + 1) % responses.size
        return response
      }
      
      private companion object {
         private const val serialVersionUID: Long = 6L
      }
    }
    
    // Create a custom DoFn that captures output
    class CapturingFn(
        httpClient: HttpClient,
        granularity: Duration,
        apiKey: String,
        private val output: MutableList<KV<String, Candle>>
    ) : TiingoCryptoFetcherFn(httpClient, granularity, apiKey) {
        
        override fun processElement(
            context: ProcessContext,
            @StateId("lastFetchedTimestamp") lastTimestampState: ValueState<StateTimestamp>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>
        ) {
            // Let the original implementation do its thing
            super.processElement(context, lastTimestampState, lastCandleState)
            
            // Capture the output for testing
            if (context.output != null && context.output.peek() != null) {
                val element = context.output.peek()
                if (element.value is Candle && element.key is String) {
                    output.add(KV.of(element.key as String, element.value as Candle))
                }
            }
        }
        
        companion object {
            private const val serialVersionUID = 7L
        }
    }
    
    val fn = CapturingFn(
        stub,
        Duration.standardDays(1),
        testApiKey,
        candles
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
    
    pipeline
        .apply(stream)
        .apply("FetchWithFillLimit", ParDo.of(fn))
    
    pipeline.run()
    
    // Now analyze our collected results
    assertThat(candles).isNotEmpty()
    
    // The total number of candles should be reasonable (not excessive fill-forward)
    // For daily data, this should be a small number - much less than the days since Oct 26, 2023
    val daysBetween = java.time.temporal.ChronoUnit.DAYS.between(
        java.time.LocalDate.of(2023, 10, 26),
        java.time.LocalDate.now()
    )
    
    // We should have significantly fewer candles than the total days between
    // Oct 26, 2023 and now - this proves fill-forward is limited
    assertThat(candles.size).isLessThan(daysBetween.toInt() / 2)
  }
}
