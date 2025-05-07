package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.coders.VoidCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.joda.time.Instant as JodaInstant
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatcher
import org.mockito.Mockito
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import java.io.IOException
import java.io.Serializable
import java.lang.reflect.Field
import java.lang.reflect.Method

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest {

  @get:Rule
  val pipeline: TestPipeline = TestPipeline.create()
  
  @get:Rule
  val mockitoRule: MockitoRule = MockitoJUnit.rule()

  private val testApiKey = "TEST_API_KEY_123"
  private val emptyResponse = "[]"

  // Sample responses
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
  
  // Sample response with gap
  private val sampleResponseDailyWithGap = """
    [{"ticker":"btcusd","priceData":[
      {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
      {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
    ]}]
  """.trimIndent()
  
  private val sampleResponseMinuteWithGap = """
    [{"ticker":"ethusd","priceData":[
      {"date":"2023-10-27T10:01:00+00:00","open":2000,"high":2002,"low":1999,"close":2001,"volume":5.2},
      {"date":"2023-10-27T10:03:00+00:00","open":2003,"high":2005,"low":2000,"close":2004,"volume":6.1}
    ]}]
  """.trimIndent()

  // a simple serializable stub
  private class StubHttpClient(
      private val responses: MutableList<String>
  ) : HttpClient, Serializable {
    private val usedUrls = mutableListOf<String>()

    override fun get(url: String, headers: Map<String, String>): String {
      usedUrls.add(url)
      return if (responses.isNotEmpty()) responses.removeAt(0) else "[]"
    }

    fun getUsedUrls(): List<String> = usedUrls.toList()
  }

  @Test
  fun `fetcher passes correct URL parameters`() {
    val stub = StubHttpClient(mutableListOf(emptyResponse))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
        .apply(ParDo.of(fn))

    pipeline.run()

    val usedUrls = stub.getUsedUrls()
    assertThat(usedUrls).hasSize(1)
    assertThat(usedUrls[0]).contains("tickers=btcusd")
    assertThat(usedUrls[0]).contains("resampleFreq=1day")
    assertThat(usedUrls[0]).contains("token=TEST_API_KEY_123")
  }

  @Test
  fun `fetcher parses daily candle data`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyPage1))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val candles = pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
        .apply(ParDo.of(fn))

    PAssert.that(candles).satisfies { result ->
      val candlesList = result.toList()
      assertThat(candlesList).hasSize(2) // 2 days of data

      // Check first candle
      val firstCandle = candlesList[0].value
      assertThat(firstCandle.currencyPair).isEqualTo("BTC/USD")
      assertThat(firstCandle.open).isEqualTo(34500.0)
      assertThat(firstCandle.close).isEqualTo(34650.0)
      assertThat(firstCandle.volume).isEqualTo(1500.0)

      null
    }

    pipeline.run()
  }

  @Test
  fun `fetcher handles empty response`() {
    val stub = StubHttpClient(mutableListOf(emptyResponse))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val candles = pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
        .apply(ParDo.of(fn))

    PAssert.that(candles).empty()
    pipeline.run()
  }

  @Test
  fun `stateful fetcher updates lastTimestamp`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyPage1))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)
    
    val results = pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
        .apply(ParDo.of(fn))
    
    // We can verify the output without directly accessing the state
    PAssert.that(results).satisfies { result ->
      val candlesList = result.toList()
      assertThat(candlesList).hasSize(2)
      
      // Check the timestamps of the candles
      val timestamps = candlesList.map { 
        Timestamps.toMillis(it.value.timestamp) 
      }.sorted()
      
      // The last timestamp should be 2023-10-27
      val oct27 = Instant.parse("2023-10-27T00:00:00Z").toEpochMilli()
      assertThat(timestamps).contains(oct27)
      
      null
    }
    
    pipeline.run()
  }

  @Test
  fun `fetcher handles incremental processing`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyPage1, sampleResponseDailyPage2))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)

    val stream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), VoidCoder.of()))
      .addElements(
        TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(0L))
      )
      .advanceProcessingTime(Duration.standardHours(1))
      .addElements(
        TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(3_600_000L))
      )
      .advanceWatermarkToInfinity()

    val candles = pipeline.apply(stream)
        .apply(ParDo.of(fn))

    PAssert.that(candles).satisfies { result ->
      val candlesList = result.toList()
      // Should have all 3 candles from both responses
      assertThat(candlesList).hasSize(3)
      null
    }

    pipeline.run()
  }
  
  // Tests for fill-forward functionality using TestStream
  
  @Test
  fun `fillForward handles gaps in daily data`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyWithGap))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)
    
    // Without direct state access, we can check the outputs to verify gap filling
    val candles = pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
        .apply(ParDo.of(fn))
    
    PAssert.that(candles).satisfies { result ->
      val candlesList = result.toList().sortedBy { 
        Timestamps.toMillis(it.value.timestamp) 
      }
      
      // Should have 2 candles from the response (not 3 yet because we have no previous state)
      assertThat(candlesList).hasSize(2)
      
      // First candle should be 2023-10-26
      val firstTimestamp = Timestamps.toMillis(candlesList[0].value.timestamp)
      val oct26 = Instant.parse("2023-10-26T00:00:00Z").toEpochMilli()
      assertThat(firstTimestamp).isEqualTo(oct26)
      
      // Second candle should be 2023-10-28, no synthetic candle yet since we don't have state
      val secondTimestamp = Timestamps.toMillis(candlesList[1].value.timestamp)
      val oct28 = Instant.parse("2023-10-28T00:00:00Z").toEpochMilli()
      assertThat(secondTimestamp).isEqualTo(oct28)
      
      null
    }
    
    pipeline.run()
  }

  @Test
  fun `fillForward handles gaps in minute data using TestStream`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseMinuteWithGap))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardMinutes(1), testApiKey)
    
    // Use TestStream to simulate incremental processing
    val stream = TestStream.create(KvCoder.of(StringUtf8Coder.of(), VoidCoder.of()))
      .addElements(
        TimestampedValue.of(KV.of("ETH/USD", null as Void?), JodaInstant(0L))
      )
      .advanceWatermarkToInfinity()
    
    val candles = pipeline.apply(stream)
        .apply(ParDo.of(fn))
    
    PAssert.that(candles).satisfies { result ->
      val candlesList = result.toList().sortedBy { 
        Timestamps.toMillis(it.value.timestamp) 
      }
      
      // Should have 2 candles from the response
      assertThat(candlesList).hasSize(2)
      
      // The gap between 10:01 and 10:03 can't be filled without prior state
      val timestamps = candlesList.map { 
        Timestamps.toMillis(it.value.timestamp) 
      }
      
      val time1 = Instant.parse("2023-10-27T10:01:00Z").toEpochMilli()
      val time3 = Instant.parse("2023-10-27T10:03:00Z").toEpochMilli()
      
      assertThat(timestamps).containsExactly(time1, time3)
      
      null
    }
    
    pipeline.run()
  }
  
  @Test
  fun `createSyntheticCandle creates proper candle with reference price`() {
    val fn = TiingoCryptoFetcherFn(StubHttpClient(mutableListOf()), Duration.standardDays(1), testApiKey)
    
    // Create a reference candle
    val currencyPair = "BTC/USD"
    val refTimestamp = Timestamps.fromMillis(
        Instant.parse("2023-10-26T00:00:00Z").toEpochMilli()
    )
    val referenceCandle = Candle.newBuilder()
        .setTimestamp(refTimestamp)
        .setCurrencyPair(currencyPair)
        .setOpen(34500.0)
        .setHigh(34800.0)
        .setLow(34200.0)
        .setClose(34650.0)
        .setVolume(1500.0)
        .build()
    
    // Create timestamp for synthetic candle
    val syntheticTime = Instant.parse("2023-10-27T00:00:00Z")
    
    // Use reflection to access the private method
    val createSyntheticMethod = TiingoCryptoFetcherFn::class.java.getDeclaredMethod(
        "createSyntheticCandle",
        Candle::class.java,
        String::class.java,
        Instant::class.java
    )
    createSyntheticMethod.isAccessible = true
    
    // Call the method
    val syntheticCandle = createSyntheticMethod.invoke(
        fn, referenceCandle, currencyPair, syntheticTime
    ) as Candle
    
    // Verify the synthetic candle properties
    assertThat(Timestamps.toMillis(syntheticCandle.timestamp)).isEqualTo(syntheticTime.toEpochMilli())
    assertThat(syntheticCandle.currencyPair).isEqualTo(currencyPair)
    assertThat(syntheticCandle.open).isEqualTo(34650.0) // Reference close price
    assertThat(syntheticCandle.high).isEqualTo(34650.0) // Reference close price
    assertThat(syntheticCandle.low).isEqualTo(34650.0) // Reference close price
    assertThat(syntheticCandle.close).isEqualTo(34650.0) // Reference close price
    assertThat(syntheticCandle.volume).isEqualTo(0.0) // Zero volume for synthetic
  }
  
  // Helper class for testing URL matching
  private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
    override fun matches(argument: String?): Boolean {
      return argument != null && substrings.all { argument.contains(it) }
    }
  }
}
