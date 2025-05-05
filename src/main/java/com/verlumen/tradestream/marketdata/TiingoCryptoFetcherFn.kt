package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.ProcessContext
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.io.Serializable
import java.time.Instant
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
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void?>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ISO_LOCAL_DATE
        private val TIINGO_DATE_FORMATTER_INTRADAY = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

        private const val LAST_FETCHED_TIMESTAMP_STATE_ID = "lastFetchedTimestamp"

        fun durationToResampleFreq(duration: Duration): String {
            return when {
                duration.standardDays >= 1   -> "${duration.standardDays}day"
                duration.standardHours >= 1  -> "${duration.standardHours}hour"
                duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
                else                         -> "1min"
            }
        }
        
        fun isDailyGranularity(duration: Duration): Boolean {
            return duration.isLongerThan(Duration.standardHours(23))
        }
    }

    // Use a simple serializable class for state
    data class StateTimestamp(val epochMillis: Long) : Serializable {
        companion object {
            fun fromProtobufTimestamp(timestamp: Timestamp): StateTimestamp {
                val millis = timestamp.getSeconds() * 1000 + timestamp.getNanos() / 1_000_000
                return StateTimestamp(millis)
            }
            
            fun toInstant(stateTimestamp: StateTimestamp): Instant {
                return Instant.ofEpochMilli(stateTimestamp.epochMillis)
            }
        }
    }

    @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID)
    private val lastTimestampSpec: StateSpec<ValueState<StateTimestamp>> =
        StateSpecs.value(SerializableCoder.of(StateTimestamp::class.java))

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID) lastTimestampState: ValueState<StateTimestamp>
    ) {
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").lowercase()
        val resampleFreq = durationToResampleFreq(granularity)

        if (apiKey.isBlank() || apiKey == "YOUR_TIINGO_API_KEY_HERE") {
            logger.atWarning().log("Invalid Tiingo API Key for %s. Skipping fetch.", currencyPair)
            return
        }

        logger.atInfo().log("Processing fetch for: %s (ticker: %s, freq: %s)", currencyPair, ticker, resampleFreq)

        // Determine start date based on state
        val lastStoredTimestamp = lastTimestampState.read()
        val startDate = if (lastStoredTimestamp != null) {
            val lastInstant = StateTimestamp.toInstant(lastStoredTimestamp)
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

        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=$resampleFreq&token=$apiKey"
        logger.atFine().log("Requesting URL: %s", url)

        var latestEpochMillis: Long = 0 // Track latest timestamp in this batch

        try {
            val response = httpClient.get(url, emptyMap())
            logger.atFine().log("Received response for %s (length: %d)", currencyPair, response.length)

            val candles = TiingoResponseParser.parseCandles(response, currencyPair)

            if (candles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s", candles.size, currencyPair)

                for (candle in candles) {
                    context.output(KV.of(currencyPair, candle))
                    
                    // Update latest timestamp tracking
                    // First, convert candle.timestamp to epochMillis
                    val candleMillis = candle.timestamp.getSeconds() * 1000 + candle.timestamp.getNanos() / 1_000_000
                    if (candleMillis > latestEpochMillis) {
                        latestEpochMillis = candleMillis
                    }
                }
            } else {
                logger.atInfo().log("No new candle data from Tiingo for %s starting %s", currencyPair, startDate)
            }

        } catch (e: IOException) {
            logger.atSevere().withCause(e).log("I/O error fetching/parsing Tiingo data for %s: %s", currencyPair, e.message)
            return
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Unexpected error fetching Tiingo data for %s: %s", currencyPair, e.message)
            return
        }

        // State update logic
        if (latestEpochMillis > 0) {
            // If we fetched new candles, update state to the latest timestamp
            val newState = StateTimestamp(latestEpochMillis)
            lastTimestampState.write(newState)
            logger.atInfo().log("Updated last timestamp state for %s to: %s",
                currencyPair, Instant.ofEpochMilli(latestEpochMillis))
        } else if (lastStoredTimestamp == null) {
            // If this was the initial fetch (no previous state) AND no data was returned,
            // set the state to the start date we tried to fetch from.
            try {
                val startInstant = if (isDailyGranularity(granularity)) {
                    LocalDate.parse(startDate, TIINGO_DATE_FORMATTER_DAILY).atStartOfDay().toInstant(ZoneOffset.UTC)
                } else {
                    try { 
                        LocalDateTime.parse(startDate, TIINGO_DATE_FORMATTER_INTRADAY).toInstant(ZoneOffset.UTC) 
                    } catch (e: Exception) { 
                        // Fallback if startDate was DEFAULT_START_DATE but granularity was intraday
                        LocalDate.parse(DEFAULT_START_DATE, TIINGO_DATE_FORMATTER_DAILY).atStartOfDay().toInstant(ZoneOffset.UTC)
                    }
                }
                val initialMillis = startInstant.toEpochMilli()
                val initialState = StateTimestamp(initialMillis)
                lastTimestampState.write(initialState)
                logger.atInfo().log("Initial fetch for %s yielded no data. Setting state to start date: %s",
                    currencyPair, startInstant)
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log("Could not parse start date '%s' to set initial state for %s", startDate, currencyPair)
            }
        }
        // If state existed but no new candles were found, state remains unchanged
    }
}
