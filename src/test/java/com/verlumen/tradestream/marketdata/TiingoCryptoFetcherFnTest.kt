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
import org.apache.beam.sdk.transforms.DoFnTester
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
      {"date":"2023-10-27T00:00:00+00:00","open":34650,"high":35000,"low":34500,"close":34950,"volume":1800}
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
        TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(0L))
      )
      .advanceProcessingTime(Duration.standardHours(1))
      .addElements(
        TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(3_600_000L))
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
  
  // New tests for fill-forward functionality

  @Test
  fun `fillMissingCandles correctly fills gaps in daily data`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseDailyWithGap))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)
    
    // Create a DoFnTester for easier testing of the fillMissingCandles method
    val tester = DoFnTester.of(fn)
    
    // Create a state with a previous candle (Oct 25)
    val currencyPair = "BTC/USD"
    val prevDay = Instant.parse("2023-10-25T00:00:00Z")
    val prevTimestamp = Timestamps.fromMillis(prevDay.toEpochMilli())
    val prevCandle = Candle.newBuilder()
        .setTimestamp(prevTimestamp)
        .setCurrencyPair(currencyPair)
        .setOpen(34400.0)
        .setHigh(34600.0)
        .setLow(34300.0)
        .setClose(34500.0)
        .setVolume(1300.0)
        .build()
    
    // Set the states in the tester
    val prevState = TiingoCryptoFetcherFn.StateTimestamp(prevDay.toEpochMilli())
    tester.setState(fn.lastTimestampSpec, prevState)
    tester.setState(fn.lastCandleSpec, prevCandle)

    // Process the element
    val input = KV.of(currencyPair, null as Void?)
    val output = tester.processBundle(listOf(input))
    
    // Verify that we get 3 candles (Oct 26, 27, 28) with Oct 27 being synthetic
    assertThat(output).hasSize(3)
    
    // Verify dates and close prices
    val timestamps = output.map { Timestamps.toMillis(it.value.timestamp) }
    val expectedTimestamps = listOf(
        Instant.parse("2023-10-26T00:00:00Z").toEpochMilli(),
        Instant.parse("2023-10-27T00:00:00Z").toEpochMilli(), // This should be synthetic
        Instant.parse("2023-10-28T00:00:00Z").toEpochMilli()
    )
    assertThat(timestamps).isEqualTo(expectedTimestamps)
    
    // Check the synthetic candle
    val syntheticCandle = output[1].value
    assertThat(syntheticCandle.volume).isEqualTo(0.0) // Synthetic candles have 0 volume
    assertThat(syntheticCandle.close).isEqualTo(34650.0) // Should be equal to Oct 26 close
  }

  @Test
  fun `fillMissingCandles correctly fills gaps in minute data`() {
    val stub = StubHttpClient(mutableListOf(sampleResponseMinuteWithGap))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardMinutes(1), testApiKey)
    
    // Create a DoFnTester for easier testing
    val tester = DoFnTester.of(fn)
    
    // Create a state with a previous candle (10:00)
    val currencyPair = "ETH/USD"
    val prevTime = Instant.parse("2023-10-27T10:00:00Z")
    val prevTimestamp = Timestamps.fromMillis(prevTime.toEpochMilli())
    val prevCandle = Candle.newBuilder()
        .setTimestamp(prevTimestamp)
        .setCurrencyPair(currencyPair)
        .setOpen(1998.0)
        .setHigh(2000.0)
        .setLow(1997.0)
        .setClose(1999.0)
        .setVolume(4.8)
        .build()
    
    // Set the states in the tester
    val prevState = TiingoCryptoFetcherFn.StateTimestamp(prevTime.toEpochMilli())
    tester.setState(fn.lastTimestampSpec, prevState)
    tester.setState(fn.lastCandleSpec, prevCandle)

    // Process the element
    val input = KV.of(currencyPair, null as Void?)
    val output = tester.processBundle(listOf(input))
    
    // Verify that we get 3 candles (10:01, 10:02, 10:03) with 10:02 being synthetic
    assertThat(output).hasSize(3)
    
    // Verify timestamps
    val timestamps = output.map { Timestamps.toMillis(it.value.timestamp) }
    val expectedTimestamps = listOf(
        Instant.parse("2023-10-27T10:01:00Z").toEpochMilli(),
        Instant.parse("2023-10-27T10:02:00Z").toEpochMilli(), // This should be synthetic
        Instant.parse("2023-10-27T10:03:00Z").toEpochMilli()
    )
    assertThat(timestamps).isEqualTo(expectedTimestamps)
    
    // Check the synthetic candle
    val syntheticCandle = output[1].value
    assertThat(syntheticCandle.volume).isEqualTo(0.0) // Synthetic candles have 0 volume
    assertThat(syntheticCandle.close).isEqualTo(2001.0)
assertThat(syntheticCandle.open).isEqualTo(2001.0)
    assertThat(syntheticCandle.high).isEqualTo(2001.0)
    assertThat(syntheticCandle.low).isEqualTo(2001.0)
  }
  
  @Test
  fun `createSyntheticCandle creates proper candle with reference price`() {
    // Create a test instance with access to the private method
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
  
  @Test
  fun `fill forward when no new data is available`() {
    // Setup a stub that returns empty response
    val stub = StubHttpClient(mutableListOf(emptyResponse))
    val fn = TiingoCryptoFetcherFn(stub, Duration.standardDays(1), testApiKey)
    
    // Create a DoFnTester
    val tester = DoFnTester.of(fn)
    
    // Create a state with a previous candle (from "yesterday")
    val currencyPair = "BTC/USD"
    val yesterday = Instant.now().minus(1, java.time.temporal.ChronoUnit.DAYS)
        .truncatedTo(java.time.temporal.ChronoUnit.DAYS)
    val yesterdayTimestamp = Timestamps.fromMillis(yesterday.toEpochMilli())
    val prevCandle = Candle.newBuilder()
        .setTimestamp(yesterdayTimestamp)
        .setCurrencyPair(currencyPair)
        .setOpen(34500.0)
        .setHigh(34800.0)
        .setLow(34200.0)
        .setClose(34650.0)
        .setVolume(1500.0)
        .build()
    
    // Set the states in the tester
    val prevState = TiingoCryptoFetcherFn.StateTimestamp(yesterday.toEpochMilli())
    tester.setState(fn.lastTimestampSpec, prevState)
    tester.setState(fn.lastCandleSpec, prevCandle)

    // Process the element
    val input = KV.of(currencyPair, null as Void?)
    val output = tester.processBundle(listOf(input))
    
    // Verify that we get a synthetic candle for today
    assertThat(output).hasSize(1)
    
    // Verify the synthetic candle
    val syntheticCandle = output[0].value
    val today = yesterday.plus(1, java.time.temporal.ChronoUnit.DAYS)
    
    assertThat(Timestamps.toMillis(syntheticCandle.timestamp)).isEqualTo(today.toEpochMilli())
    assertThat(syntheticCandle.volume).isEqualTo(0.0) // Zero volume for synthetic
    assertThat(syntheticCandle.close).isEqualTo(34650.0) // Should maintain previous close
  }
  
  // Helper class for testing URL matching
  private class UrlMatcher(vararg val substrings: String) : ArgumentMatcher<String> {
    override fun matches(argument: String?): Boolean {
      return argument != null && substrings.all { argument.contains(it) }
    }
  }
}
