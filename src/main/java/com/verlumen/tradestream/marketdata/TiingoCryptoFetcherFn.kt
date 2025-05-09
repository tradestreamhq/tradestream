package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import java.io.IOException
import java.io.Serializable
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.ProcessContext
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration

/**
 * A stateful DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency
 * pair. Fetches incrementally and fills forward missing candles.
 */
class TiingoCryptoFetcherFn
@Inject
constructor(
    private val httpClient: HttpClient,
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void?>, KV<String, Candle>>() {

  companion object {
    private val logger = FluentLogger.forEnclosingClass()

    internal val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ofPattern("yyyy-MM-dd")
    internal val TIINGO_DATE_FORMATTER_INTRADAY = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

    private const val DEFAULT_START_DATE = "2019-01-02"
    private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

    fun durationToResampleFreq(duration: Duration): String {
      return when {
        duration.standardDays >= 1 -> "${duration.standardDays}day"
        duration.standardHours >= 1 -> "${duration.standardHours}hour"
        duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
        else -> "1min"
      }
    }

    fun isDailyGranularity(duration: Duration): Boolean = duration.standardDays >= 1

    fun durationToTemporalUnit(duration: Duration): ChronoUnit =
        when {
          duration.standardDays >= 1 -> ChronoUnit.DAYS
          duration.standardHours >= 1 -> ChronoUnit.HOURS
          else -> ChronoUnit.MINUTES
        }

    fun durationToAmount(duration: Duration): Long =
        when {
          duration.standardDays >= 1 -> duration.standardDays
          duration.standardHours >= 1 -> duration.standardHours
          else -> duration.standardMinutes
        }
  }

  /** Simple serializable wrapper for the last fetch timestamp */
  class StateTimestamp(val timestamp: Long) : Serializable {
    constructor() : this(0L)

    override fun toString() = "StateTimestamp[$timestamp]"

    companion object {
      private const val serialVersionUID = 1L
    }
  }

  @StateId("lastFetchedTimestamp")
  internal val lastTimestampSpec: StateSpec<ValueState<StateTimestamp>> =
      StateSpecs.value(SerializableCoder.of(StateTimestamp::class.java))

  @StateId("lastCandle")
  internal val lastCandleSpec: StateSpec<ValueState<Candle>> =
      StateSpecs.value(ProtoCoder.of(Candle::class.java))

  @ProcessElement
  fun processElement(
      context: ProcessContext,
      @StateId("lastFetchedTimestamp") lastTimestampState: ValueState<StateTimestamp>,
      @StateId("lastCandle") lastCandleState: ValueState<Candle>
  ) {
    val currencyPair = context.element().key
    val ticker = currencyPair.replace("/", "").lowercase()

    if (apiKey.isBlank()) {
      logger.atWarning().log("Skipping Tiingo fetch for %s: Empty API key", currencyPair)
      return
    }

    val resampleFreq = durationToResampleFreq(granularity)
    logger.atInfo().log(
        "Processing fetch for: %s (ticker: %s, freq: %s)", currencyPair, ticker, resampleFreq)

    // Determine the start date based on saved state
    val lastState = lastTimestampState.read()
    val startDate =
        if (lastState != null && lastState.timestamp > 0) {
          val lastInst = Instant.ofEpochMilli(lastState.timestamp)
          if (isDailyGranularity(granularity)) {
            // Fetch data starting the day AFTER the last fetched day's timestamp
            LocalDate.ofInstant(lastInst, ZoneOffset.UTC)
                .plusDays(1)
                .format(TIINGO_DATE_FORMATTER_DAILY)
          } else {
            // Fetch data starting 1 second AFTER the last fetched timestamp
            LocalDateTime.ofInstant(lastInst.plusSeconds(1), ZoneOffset.UTC)
                .format(TIINGO_DATE_FORMATTER_INTRADAY)
          }
        } else {
          DEFAULT_START_DATE
        }

    val url =
        "$TIINGO_API_URL?tickers=$ticker" +
            "&startDate=$startDate" +
            "&resampleFreq=$resampleFreq" +
            "&token=$apiKey"
    logger.atFine().log("Requesting URL: %s", url)

    var latestFetchedEpochMillis = 0L // Track latest timestamp from *fetched* data
    var currentLast: Candle? = lastCandleState.read()

    try {
      val response = httpClient.get(url, emptyMap())
      val fetched = TiingoResponseParser.parseCandles(response, currencyPair)

      if (fetched.isNotEmpty()) {
        logger.atInfo().log("Parsed %d candles for %s", fetched.size, currencyPair)

        val toEmit = fillMissingCandles(fetched, currentLast)
        toEmit.forEach { candle ->
          context.output(KV.of(currencyPair, candle))
          currentLast = candle // Update currentLast after each emission

          // Only update latestFetchedEpochMillis if it's a real candle
          if (fetched.any { it.timestamp == candle.timestamp && it.volume > 0.0 }) {
            val m = candle.timestamp.seconds * 1000 + candle.timestamp.nanos / 1_000_000
            if (m > latestFetchedEpochMillis) latestFetchedEpochMillis = m
          }
        }
      } else {
        logger.atInfo().log(
            "No new candle data from Tiingo for %s starting %s", currencyPair, startDate)
        // If no fetched candles but we have a last candle, fill forward
        currentLast?.let { lastCandle ->
          val now = Instant.now()
          val unit = durationToTemporalUnit(granularity)
          val amt = durationToAmount(granularity)
          var nextExpected =
              Instant.ofEpochSecond(
                      lastCandle.timestamp.seconds, lastCandle.timestamp.nanos.toLong())
                  .plus(amt, unit)

          while (nextExpected.isBefore(now)) {
            logger.atFine().log(
                "API returned no data, filling forward for %s at %s", currencyPair, nextExpected)
            val synth = createSyntheticCandle(lastCandle, currencyPair, nextExpected)
            context.output(KV.of(currencyPair, synth))
            currentLast = synth // Update currentLast after emitting synthetic candle
            nextExpected = nextExpected.plus(amt, unit)
          }
        }
      }
    } catch (ioe: IOException) {
      logger.atWarning().withCause(ioe).log(
          "Error fetching data from Tiingo for %s", currencyPair)
      return
    } catch (ex: Exception) {
      logger.atSevere().withCause(ex).log("Unexpected error processing %s", currencyPair)
      return
    }

    // Determine the timestamp of the very last emitted candle (real or synthetic)
    val finalEmittedTimestampMillis =
        currentLast?.let { candle ->
          candle.timestamp.seconds * 1000 + candle.timestamp.nanos / 1_000_000
        }
            ?: lastTimestampState.read()?.timestamp ?: 0L // Use previous state if nothing emitted

    // Update timestamp state based on the last *emitted* candle's timestamp
    if (finalEmittedTimestampMillis > 0) {
      val existing = lastTimestampState.read()
      // Update state if it's newer than the existing state OR if state was previously null
      if (existing == null || existing.timestamp < finalEmittedTimestampMillis) {
        lastTimestampState.write(StateTimestamp(finalEmittedTimestampMillis))
        logger.atInfo().log(
            "Updated last timestamp state for %s to: %d (based on last emitted)",
            currencyPair,
            finalEmittedTimestampMillis)
      }
    } else if (lastTimestampState.read() == null) {
      // Initialize if never set and nothing was fetched/filled
      try {
        val initMillis =
            if (isDailyGranularity(granularity)) {
              LocalDate.parse(startDate, TIINGO_DATE_FORMATTER_DAILY)
                  .atStartOfDay()
                  .toInstant(ZoneOffset.UTC)
                  .toEpochMilli()
            } else {
              LocalDateTime.parse(startDate, TIINGO_DATE_FORMATTER_INTRADAY)
                  .toInstant(ZoneOffset.UTC)
                  .toEpochMilli()
            }
        lastTimestampState.write(StateTimestamp(initMillis))
        logger.atInfo().log(
            "Initialized state for %s with start date: %s", currencyPair, startDate)
      } catch (e: Exception) {
        logger.atWarning().withCause(e).log(
            "Could not parse start date '%s' to set initial state for %s", startDate, currencyPair)
      }
    }

    // Persist last emitted candle
    currentLast?.let { lastCandleState.write(it) }
  }

  /**
   * Fill gaps between fetched candles using the last known candle as reference. If lastKnownCandle
   * is null, simply return fetched.
   */
  private fun fillMissingCandles(
      fetched: List<Candle>,
      lastKnownCandle: Candle?
  ): List<Candle> {
    if (lastKnownCandle == null) return fetched
    if (fetched.isEmpty()) return emptyList()

    val unit = durationToTemporalUnit(granularity)
    val amt = durationToAmount(granularity)
    val out = mutableListOf<Candle>()
    var prev: Candle = lastKnownCandle

    for (curr in fetched) {
      val currTime =
          Instant.ofEpochSecond(curr.timestamp.seconds, curr.timestamp.nanos.toLong())
      var nextExpected =
          Instant.ofEpochSecond(prev.timestamp.seconds, prev.timestamp.nanos.toLong())
              .plus(amt, unit)

      while (nextExpected.isBefore(currTime)) {
        logger.atFine().log(
            "Filling gap for %s at %s (before %s)", curr.currencyPair, nextExpected, currTime)
        val synth = createSyntheticCandle(prev, curr.currencyPair, nextExpected)
        out.add(synth)
        prev = synth // Update prev to the synthetic candle
        nextExpected = nextExpected.plus(amt, unit)
      }
      out.add(curr)
      prev = curr // Update prev to the current fetched candle
    }
    return out
  }

  /** Create a zero-volume synthetic candle using the reference candle's close price. */
  private fun createSyntheticCandle(
      reference: Candle,
      currencyPair: String,
      timestamp: Instant
  ): Candle {
    val tsProto = Timestamps.fromMillis(timestamp.toEpochMilli())
    val price = reference.close // Use the close price of the *reference* candle
    return Candle.newBuilder()
        .setTimestamp(tsProto)
        .setCurrencyPair(currencyPair)
        .setOpen(price)
        .setHigh(price)
        .setLow(price)
        .setClose(price)
        .setVolume(0.0)
        .build()
  }
}
