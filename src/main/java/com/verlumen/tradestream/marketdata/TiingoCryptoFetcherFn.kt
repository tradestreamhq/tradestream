package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Timestamp // Import protobuf timestamp
import com.google.protobuf.util.Timestamps // Import Timestamps utility
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.SerializableCoder // Import SerializableCoder
import org.apache.beam.sdk.state.StateSpec // Import StateSpec
import org.apache.beam.sdk.state.StateSpecs // Import StateSpecs
import org.apache.beam.sdk.state.ValueState // Import ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.ProcessContext
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId // Import StateId annotation
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.io.Serializable
import java.time.Instant // Using java.time for calculations
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * A stateful DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 * This version includes state management to fetch incrementally.
 */
class TiingoCryptoFetcherFn @Inject constructor(
    private val httpClient: HttpClient,
    // Temporary direct constructor args
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void?>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ISO_LOCAL_DATE // YYYY-MM-dd
        private val TIINGO_DATE_FORMATTER_INTRADAY = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss") // YYYY-MM-ddTHH:mm:ss

        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

        // State ID for storing the timestamp of the last fetched candle
        private const val LAST_FETCHED_TIMESTAMP_STATE_ID = "lastFetchedTimestamp"


        fun durationToResampleFreq(duration: Duration): String { /* ... same as PR 2 ... */
             return when {
                duration.standardDays >= 1   -> "${duration.standardDays}day"
                duration.standardHours >= 1  -> "${duration.standardHours}hour"
                duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
                else                         -> "1min"
            }
        }
        fun isDailyGranularity(duration: Duration): Boolean { /* ... same as PR 2 ... */
            return duration.isLongerThan(Duration.standardHours(23))
        }
    }

    // --- State Declaration ---
    @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID)
    private val lastTimestampSpec: StateSpec<ValueState<Timestamp>> =
        StateSpecs.value(SerializableCoder.forClass(Timestamp::class.java)) // Use SerializableCoder for Timestamp state

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID) lastTimestampState: ValueState<Timestamp> // Inject state
    ) {
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").lowercase()
        val resampleFreq = durationToResampleFreq(granularity)

        if (apiKey.isBlank() || apiKey == "YOUR_TIINGO_API_KEY_HERE") {
            logger.atWarning().log("Invalid Tiingo API Key for %s. Skipping fetch.", currencyPair)
            return
        }

        logger.atInfo().log("Processing fetch for: %s (ticker: %s, freq: %s)", currencyPair, ticker, resampleFreq)

        // --- Determine Start Date based on State ---
        val lastTimestamp = lastTimestampState.read()
        val startDate = if (lastTimestamp != null && lastTimestamp.getSeconds() > 0) {
             val lastInstant = Instant.ofEpochSecond(lastTimestamp.getSeconds(), lastTimestamp.getNanos().toLong())
            logger.atFine().log("Found previous state for %s: %s", currencyPair, lastInstant)

            if (isDailyGranularity(granularity)) {
                // For daily, start from the day *after*
                val nextDay = LocalDate.ofInstant(lastInstant, ZoneOffset.UTC).plusDays(1)
                nextDay.format(TIINGO_DATE_FORMATTER_DAILY)
            } else {
                // For intraday, start from the exact timestamp + 1 second
                val nextTime = LocalDateTime.ofInstant(lastInstant, ZoneOffset.UTC).plusSeconds(1)
                nextTime.format(TIINGO_DATE_FORMATTER_INTRADAY)
            }
        } else {
            logger.atInfo().log("No previous state for %s. Using default start date: %s", currencyPair, DEFAULT_START_DATE)
            DEFAULT_START_DATE
        }
        // --- End Start Date Logic ---

        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=$resampleFreq&token=$apiKey"
        logger.atFine().log("Requesting URL: %s", url)

        var latestCandleInBatchTimestamp: Timestamp? = null // Track latest timestamp in *this* batch
        val fetchedCandles: List<Candle> // Declare fetchedCandles here

        try {
            val response = httpClient.get(url, emptyMap())
            logger.atFine().log("Received response for %s (length: %d)", currencyPair, response.length)

            fetchedCandles = TiingoResponseParser.parseCandles(response, currencyPair) // Assign here

            if (fetchedCandles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s", fetchedCandles.size, currencyPair)

                fetchedCandles.forEach { candle ->
                    context.output(KV.of(currencyPair, candle))
                    // Track the latest timestamp encountered in this batch
                    if (latestCandleInBatchTimestamp == null || Timestamps.compare(candle.timestamp, latestCandleInBatchTimestamp!!) > 0) {
                        latestCandleInBatchTimestamp = candle.timestamp
                    }
                }
            } else {
                logger.atInfo().log("No new candle data from Tiingo for %s starting %s", currencyPair, startDate)
            }

        } catch (e: IOException) {
            logger.atSevere().withCause(e).log("I/O error fetching/parsing Tiingo data for %s: %s", currencyPair, e.message)
            return // Stop processing this element on error
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Unexpected error fetching Tiingo data for %s: %s", currencyPair, e.message)
             return // Stop processing this element on error
        }

        // --- State Update Logic ---
        if (latestCandleInBatchTimestamp != null) {
            // If we fetched new candles, update state to the latest timestamp from the batch
            lastTimestampState.write(latestCandleInBatchTimestamp)
            logger.atInfo().log("Updated last timestamp state for %s to: %s",
                 currencyPair, Timestamps.toString(latestCandleInBatchTimestamp))
        } else if (lastTimestamp == null && fetchedCandles.isEmpty()) {
            // If this was the *initial* fetch (lastTimestamp was null) AND no data was returned,
            // set the state to the start date we *tried* to fetch from. This prevents
            // repeatedly querying the full history from DEFAULT_START_DATE.
             try {
                val startInstant = if (isDailyGranularity(granularity)) {
                    LocalDate.parse(startDate, TIINGO_DATE_FORMATTER_DAILY).atStartOfDay().toInstant(ZoneOffset.UTC)
                } else {
                     try { LocalDateTime.parse(startDate, TIINGO_DATE_FORMATTER_INTRADAY).toInstant(ZoneOffset.UTC) }
                     catch (e: Exception) { // Fallback if startDate was DEFAULT_START_DATE but granularity was intraday
                         LocalDate.parse(DEFAULT_START_DATE, TIINGO_DATE_FORMATTER_DAILY).atStartOfDay().toInstant(ZoneOffset.UTC)
                     }
                }
                val initialTimestamp = Timestamps.fromMillis(startInstant.toEpochMilli()) // Convert java.time.Instant to proto Timestamp
                lastTimestampState.write(initialTimestamp)
                 logger.atInfo().log("Initial fetch for %s yielded no data. Setting state to start date: %s",
                      currencyPair, Timestamps.toString(initialTimestamp))
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log("Could not parse start date '%s' to set initial state for %s", startDate, currencyPair)
            }
        }
        // If lastTimestamp existed but no new candles were found, the state remains unchanged.
        // --- End State Update Logic ---
    }
}
