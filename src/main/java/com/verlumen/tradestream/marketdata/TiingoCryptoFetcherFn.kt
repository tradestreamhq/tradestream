package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.io.Serializable
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/**
 * A stateful DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 * Fetches incrementally and fills forward missing candles.
 */
class TiingoCryptoFetcherFn @Inject constructor(
    private val httpClient: HttpClient,
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void?>, KV<String, Candle>>() {

    private val logger = FluentLogger.forEnclosingClass()

    companion object {
        // Date/time formatters to use with Tiingo API
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ofPattern("yyyy-MM-dd")
        private val TIINGO_DATE_FORMATTER_INTRADAY = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

        // State IDs
        private const val LAST_FETCHED_TIMESTAMP_STATE_ID = "lastFetchedTimestamp"
        // State ID for storing the last candle (used for filling forward)
        private const val LAST_CANDLE_STATE_ID = "lastCandle"

        fun durationToResampleFreq(duration: Duration): String {
            return when {
                duration.standardDays >= 1   -> "${duration.standardDays}day"
                duration.standardHours >= 1  -> "${duration.standardHours}hour"
                duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
                else                         -> "1min" // Default or error case
            }
        }

        fun isDailyGranularity(duration: Duration): Boolean {
            return duration.isLongerThan(Duration.standardHours(23))
        }
        
        /** Convert a Joda Duration to a java.time.temporal.TemporalUnit. */
        fun durationToTemporalUnit(duration: Duration): ChronoUnit {
            return when {
                duration.standardDays >= 1 -> ChronoUnit.DAYS
                duration.standardHours >= 1 -> ChronoUnit.HOURS
                else -> ChronoUnit.MINUTES
            }
        }

        /** Get the amount for the temporal unit based on the Joda Duration. */
        fun durationToAmount(duration: Duration): Long {
            return when {
                duration.standardDays >= 1 -> duration.standardDays
                duration.standardHours >= 1 -> duration.standardHours
                else -> duration.standardMinutes
            }
        }
    }

    // Use a simple serializable class for state
    data class StateTimestamp(val epochMillis: Long) : Serializable {
        companion object {
            // Fixed the parameter type to avoid ambiguity
            fun fromProtobufTimestamp(protoTimestamp: com.google.protobuf.Timestamp): StateTimestamp {
                val millis = Timestamps.toMillis(protoTimestamp)
                return StateTimestamp(millis)
            }

            fun toInstant(stateTimestamp: StateTimestamp): Instant {
                return Instant.ofEpochMilli(stateTimestamp.epochMillis)
            }
        }
    }

    @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID)
    internal val lastTimestampSpec: StateSpec<ValueState<StateTimestamp>> =
        StateSpecs.value(SerializableCoder.of(StateTimestamp::class.java))
        
    // New state for last emitted candle
    @StateId(LAST_CANDLE_STATE_ID)
    internal val lastCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID) lastTimestampState: ValueState<StateTimestamp>,
        @StateId(LAST_CANDLE_STATE_ID) lastCandleState: ValueState<Candle> // Added new state parameter
    ) {
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").lowercase()

        // Skip processing if API key is missing or empty
        if (apiKey.isBlank()) {
            logger.atWarning().log("Skipping Tiingo fetch for %s: Empty API key", currencyPair)
            return
        }

        val resampleFreq = durationToResampleFreq(granularity)

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

        // Construct the URL
        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=$resampleFreq&token=$apiKey"
        logger.atFine().log("Requesting URL: %s", url)

        var latestEpochMillis: Long = 0 // Track latest timestamp in this batch
        var currentLastEmittedCandle: Candle? = lastCandleState.read() // Get last emitted candle

        try {
            val response = httpClient.get(url, emptyMap())
            logger.atFine().log("Received response for %s (length: %d)", currencyPair, response.length)

            val fetchedCandles = TiingoResponseParser.parseCandles(response, currencyPair)

            if (fetchedCandles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s", fetchedCandles.size, currencyPair)

                // Process with Fill-Forward
                val candlesToOutput = fillMissingCandles(fetchedCandles, currentLastEmittedCandle, currencyPair)
                
                candlesToOutput.forEach { candle ->
                    context.output(KV.of(currencyPair, candle))
                    currentLastEmittedCandle = candle // Update last emitted candle locally
                    
                    // Update latest timestamp tracking (only for real candles)
                    if (fetchedCandles.any { it.timestamp == candle.timestamp && it.volume > 0.0 }) {
                        val candleMillis = candle.timestamp.seconds * 1000 + candle.timestamp.nanos / 1_000_000
                        if (candleMillis > latestEpochMillis) {
                            latestEpochMillis = candleMillis
                        }
                    }
                }

            } else {
                logger.atInfo().log("No new candle data from Tiingo for %s starting %s", currencyPair, startDate)
                
                // Fill forward if no new data but time has passed
                if (currentLastEmittedCandle != null) {
                    val now = Instant.now()
                    val lastCandleInstant = Instant.ofEpochSecond(
                        currentLastEmittedCandle!!.timestamp.seconds,
                        currentLastEmittedCandle!!.timestamp.nanos.toLong()
                    )
                    val temporalUnit = durationToTemporalUnit(granularity)
                    val amount = durationToAmount(granularity)
                    var nextExpectedTime = lastCandleInstant.plus(amount, temporalUnit)

                    val filledCandles = mutableListOf<Candle>()
                    while (nextExpectedTime.isBefore(now)) {
                        logger.atFine().log("API returned no data, filling forward for %s at %s", currencyPair, nextExpectedTime)
                        val syntheticCandle = createSyntheticCandle(currentLastEmittedCandle!!, currencyPair, nextExpectedTime)
                        filledCandles.add(syntheticCandle)
                        currentLastEmittedCandle = syntheticCandle // Update last emitted locally
                        nextExpectedTime = nextExpectedTime.plus(amount, temporalUnit)
                    }
                    // Output any generated synthetic candles
                    filledCandles.forEach { context.output(KV.of(currencyPair, it)) }
                }
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
        
        // Update the last emitted candle state
        if (currentLastEmittedCandle != null) {
            lastCandleState.write(currentLastEmittedCandle)
            logger.atFine().log("Updated last emitted candle state for %s to candle at: %s",
                currencyPair, Timestamps.toString(currentLastEmittedCandle!!.timestamp))
        }
    }
    
    /**
     * Fill missing candles between fetched candles, starting from the last known candle.
     */
    private fun fillMissingCandles(
        fetchedCandles: List<Candle>,
        lastKnownCandle: Candle?, // Last candle *emitted* (could be synthetic)
        currencyPair: String
    ): List<Candle> {
        if (fetchedCandles.isEmpty()) return emptyList()

        val result = mutableListOf<Candle>()
        val temporalUnit = durationToTemporalUnit(granularity)
        val amount = durationToAmount(granularity)

        var previousCandle = lastKnownCandle // Start reference point

        for (currentFetchedCandle in fetchedCandles) {
            val currentFetchedInstant = Instant.ofEpochSecond(
                currentFetchedCandle.timestamp.seconds,
                currentFetchedCandle.timestamp.nanos.toLong()
            )

            if (previousCandle != null) {
                val prevInstant = Instant.ofEpochSecond(
                    previousCandle.timestamp.seconds,
                    previousCandle.timestamp.nanos.toLong()
                )

                // Calculate the next expected time based on the previous candle
                var expectedTime = prevInstant.plus(amount, temporalUnit)

                // While the next expected time is before the current *fetched* candle's time, fill the gap
                while (expectedTime.isBefore(currentFetchedInstant)) {
                    logger.atFine().log("Filling gap for %s at expected time %s (before %s)",
                        currencyPair, expectedTime, currentFetchedInstant)
                    // Use previousCandle (which could be the last known or a previously generated synthetic one) as reference
                    val syntheticCandle = createSyntheticCandle(previousCandle, currencyPair, expectedTime)
                    result.add(syntheticCandle)
                    previousCandle = syntheticCandle // Update prevCandle to the newly created synthetic one
                    expectedTime = expectedTime.plus(amount, temporalUnit) // Move to next expected time
                }
            }

            // Add the actual fetched candle from Tiingo
            result.add(currentFetchedCandle)
            previousCandle = currentFetchedCandle // Update prevCandle to this fetched candle
        }

        return result
    }
    
    /**
     * Create a synthetic candle based on a reference candle.
     */
    private fun createSyntheticCandle(
        referenceCandle: Candle, // The last candle (real or synthetic) before the gap
        currencyPair: String,
        timestamp: Instant // java.time.Instant
    ): Candle {
        val protoTimestamp = Timestamps.fromMillis(timestamp.toEpochMilli())
        // Use the close price from reference candle for all price fields
        val price = referenceCandle.close

        return Candle.newBuilder()
            .setTimestamp(protoTimestamp)
            .setCurrencyPair(currencyPair)
            .setOpen(price)
            .setHigh(price)
            .setLow(price)
            .setClose(price)
            .setVolume(0.0) // Zero volume indicates synthetic candle
            .build()
    }
}
