package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/**
 * Factory interface for creating TiingoCryptoFetcherFn instances with different granularities and API keys.
 */
interface TiingoCryptoFetcherFnFactory {
    fun create(
        @Assisted("granularity") granularity: Duration,
        @Assisted("apiKey") apiKey: String
    ): TiingoCryptoFetcherFn
}

/**
 * A stateful DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 */
class TiingoCryptoFetcherFn @AssistedInject constructor(
    private val httpClient: HttpClient,
    @Assisted("granularity") private val granularity: Duration,
    @Assisted("apiKey") private val apiKey: String // Injected API Key
) : DoFn<KV<String, Void>, KV<String, Candle>>() {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ISO_LOCAL_DATE
        private val TIINGO_DATE_FORMATTER_INTRADAY = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
        private const val LAST_FETCHED_TIMESTAMP_STATE_ID = "lastFetchedTimestamp"
        private const val LAST_CANDLE_STATE_ID = "lastCandle"
        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL = "[https://api.tiingo.com/tiingo/crypto/prices](https://api.tiingo.com/tiingo/crypto/prices)"

        // Factory interface for Assisted Injection
        interface Factory : TiingoCryptoFetcherFnFactory

        fun durationToResampleFreq(duration: Duration): String { /* ... (same as before) ... */ }
        fun isDailyGranularity(duration: Duration): Boolean { /* ... (same as before) ... */ }
        fun durationToTemporalUnit(duration: Duration): ChronoUnit { /* ... (same as before) ... */ }
        fun durationToAmount(duration: Duration): Long { /* ... (same as before) ... */ }
    }

    @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID)
    private val lastTimestampSpec: StateSpec<ValueState<Timestamp>> =
        StateSpecs.value<Timestamp>(ProtoCoder.of(Timestamp::class.java))

    @StateId(LAST_CANDLE_STATE_ID)
    private val lastCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value<Candle>(ProtoCoder.of(Candle::class.java))

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID) lastTimestampState: ValueState<Timestamp>,
        @StateId(LAST_CANDLE_STATE_ID) lastCandleState: ValueState<Candle>
    ) {
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").toLowerCase()
        val resampleFreq = durationToResampleFreq(granularity)

        // Validate API Key before proceeding
        if (apiKey.isBlank() || apiKey == "YOUR_TIINGO_API_KEY_HERE") {
             logger.atSevere().log("Tiingo API Key is missing or invalid for pair %s. Skipping fetch.", currencyPair)
             return // Do not proceed without a valid key
        }


        logger.atInfo().log("Fetching Tiingo data for: %s (ticker: %s) with granularity: %s",
            currencyPair, ticker, resampleFreq)

        val lastProcessedTimestamp = lastTimestampState.read()
        val startDate = if (lastProcessedTimestamp != null && lastProcessedTimestamp.seconds > 0) {
            // ... (start date logic remains the same) ...
             val lastInstant = Instant.ofEpochSecond(lastProcessedTimestamp.seconds, lastProcessedTimestamp.nanos.toLong())
            if (isDailyGranularity(granularity)) {
                val nextDay = LocalDate.ofInstant(lastInstant, ZoneOffset.UTC).plusDays(1)
                nextDay.format(TIINGO_DATE_FORMATTER_DAILY)
            } else {
                val nextTime = LocalDateTime.ofInstant(lastInstant, ZoneOffset.UTC).plusSeconds(1)
                nextTime.format(TIINGO_DATE_FORMATTER_INTRADAY)
            }
        } else {
            logger.atInfo().log("No previous state for %s. Using default start date: %s", currencyPair, DEFAULT_START_DATE)
            DEFAULT_START_DATE
        }

        // Construct API URL using the injected apiKey
        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=$resampleFreq&token=$apiKey" // Use injected apiKey
        logger.atFine().log("Requesting URL: %s", url)

        var latestCandleInBatchTimestamp: Timestamp? = null
        var lastEmittedCandle: Candle? = lastCandleState.read()

        try {
            val response = httpClient.get(url, emptyMap())
             logger.atFine().log("Received response for %s (length: %d)", currencyPair, response.length)

            val fetchedCandles = TiingoResponseParser.parseCandles(response, currencyPair)

            // --- Fill Forward and Output Logic (remains the same as previous version) ---
             if (fetchedCandles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s with granularity %s",
                    fetchedCandles.size, currencyPair, resampleFreq)
                val candlesToOutput = fillMissingCandles(fetchedCandles, lastEmittedCandle, currencyPair)
                candlesToOutput.forEach { candle ->
                    context.output(KV.of(currencyPair, candle))
                    lastEmittedCandle = candle
                     if (fetchedCandles.any { it.timestamp == candle.timestamp }) {
                         if (latestCandleInBatchTimestamp == null || Timestamps.compare(candle.timestamp, latestCandleInBatchTimestamp!!) > 0) {
                            latestCandleInBatchTimestamp = candle.timestamp
                        }
                    }
                }
            } else {
                 logger.atInfo().log("No new candle data from Tiingo for %s starting %s", currencyPair, startDate)
                 if (lastEmittedCandle != null) {
                    val now = Instant.now()
                    val lastCandleInstant = Instant.ofEpochSecond(lastEmittedCandle!!.timestamp.seconds, lastEmittedCandle!!.timestamp.nanos.toLong())
                    val temporalUnit = durationToTemporalUnit(granularity)
                    val amount = durationToAmount(granularity)
                    var nextExpectedTime = lastCandleInstant.plus(amount, temporalUnit)
                    while (nextExpectedTime.isBefore(now)) {
                        logger.atFine().log("Filling forward for %s at expected time %s", currencyPair, nextExpectedTime)
                        val syntheticCandle = createSyntheticCandle(lastEmittedCandle!!, currencyPair, nextExpectedTime)
                        context.output(KV.of(currencyPair, syntheticCandle))
                        lastEmittedCandle = syntheticCandle
                        nextExpectedTime = nextExpectedTime.plus(amount, temporalUnit)
                    }
                }
            }
            // --- End Fill Forward and Output Logic ---

        } catch (e: IOException) {
            logger.atSevere().withCause(e).log("Failed to fetch/parse Tiingo data for %s from URL: %s", currencyPair, url)
            return
        }

        // --- State Update (remains the same as previous version) ---
        if (latestCandleInBatchTimestamp != null) {
            lastTimestampState.write(latestCandleInBatchTimestamp)
            logger.atInfo().log("Updated last processed timestamp state for %s to: %s", currencyPair, Timestamps.toString(latestCandleInBatchTimestamp))
        } else if (lastProcessedTimestamp == null && fetchedCandles.isEmpty()) {
             try {
                val startInstant = if (isDailyGranularity(granularity)) { LocalDate.parse(startDate, TIINGO_DATE_FORMATTER_DAILY).atStartOfDay().toInstant(ZoneOffset.UTC) }
                                 else { try { LocalDateTime.parse(startDate, TIINGO_DATE_FORMATTER_INTRADAY).toInstant(ZoneOffset.UTC) }
                                        catch (e: Exception) { LocalDate.parse(DEFAULT_START_DATE, TIINGO_DATE_FORMATTER_DAILY).atStartOfDay().toInstant(ZoneOffset.UTC) } }
                val initialTimestamp = Timestamps.fromMillis(startInstant.toEpochMilli())
                lastTimestampState.write(initialTimestamp)
                 logger.atInfo().log("Initial fetch %s yielded no data. Setting last processed timestamp to start date: %s", currencyPair, Timestamps.toString(initialTimestamp))
            } catch (e: Exception) { logger.atWarning().withCause(e).log("Could not parse start date '%s' to set initial state for %s", startDate, currencyPair) }
        }
         if (lastEmittedCandle != null) {
            lastCandleState.write(lastEmittedCandle)
             logger.atFine().log("Updated last emitted candle state for %s to candle at: %s", currencyPair, Timestamps.toString(lastEmittedCandle!!.timestamp))
        }
        // --- End State Update ---
    }

     // fillMissingCandles and createSyntheticCandle methods remain the same
    private fun fillMissingCandles(fetchedCandles: List<Candle>, lastKnownCandle: Candle?, currencyPair: String): List<Candle> { /* ... Same as before ... */
        if (fetchedCandles.isEmpty()) return emptyList()
        val result = mutableListOf<Candle>()
        val temporalUnit = durationToTemporalUnit(granularity)
        val amount = durationToAmount(granularity)
        var prevCandle = lastKnownCandle
        for (currentFetchedCandle in fetchedCandles) {
            val currentFetchedInstant = Instant.ofEpochSecond(currentFetchedCandle.timestamp.seconds, currentFetchedCandle.timestamp.nanos.toLong())
            if (prevCandle != null) {
                val prevInstant = Instant.ofEpochSecond(prevCandle.timestamp.seconds, prevCandle.timestamp.nanos.toLong())
                var expectedTime = prevInstant.plus(amount, temporalUnit)
                while (expectedTime.isBefore(currentFetchedInstant)) {
                    logger.atFine().log("Filling gap for %s at expected time %s (before %s)", currencyPair, expectedTime, currentFetchedInstant)
                    val syntheticCandle = createSyntheticCandle(prevCandle, currencyPair, expectedTime)
                    result.add(syntheticCandle)
                    prevCandle = syntheticCandle
                    expectedTime = expectedTime.plus(amount, temporalUnit)
                }
            }
            result.add(currentFetchedCandle)
            prevCandle = currentFetchedCandle
        }
        return result
     }
    private fun createSyntheticCandle(referenceCandle: Candle, currencyPair: String, timestamp: Instant): Candle { /* ... Same as before ... */
         val protoTimestamp = Timestamps.fromMillis(timestamp.toEpochMilli())
        val price = referenceCandle.close
        return Candle.newBuilder()
            .setTimestamp(protoTimestamp)
            .setCurrencyPair(currencyPair)
            .setOpen(price)
            .setHigh(price)
            .setLow(price)
            .setClose(price)
            .setVolume(0.0)
            .build()
     }
}
