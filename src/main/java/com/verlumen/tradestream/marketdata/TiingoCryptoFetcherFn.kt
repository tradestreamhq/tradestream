package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import java.io.IOException
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * A stateful DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 *
 * It maintains the timestamp of the last successfully fetched candle to only request newer data
 * on subsequent triggers.
 */
class TiingoCryptoFetcherFn @Inject constructor(
    private val httpClient: HttpClient
    // Consider injecting API key provider here for better security
) : DoFn<KV<String, Void>, Candle>() { // Input is Keyed Void, Output is Candle

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE // YYYY-MM-DD

        // State ID for storing the timestamp of the last fetched candle
        private const val LAST_FETCHED_TIMESTAMP_STATE_ID = "lastFetchedTimestamp"

        // Default historical start date if no state exists
        private const val DEFAULT_START_DATE = "2019-01-02"

        // Tiingo API endpoint (base)
        private const val TIINGO_API_URL = "[https://api.tiingo.com/tiingo/crypto/prices](https://api.tiingo.com/tiingo/crypto/prices)"

        // Replace with your actual Tiingo API Key or inject it securely
        private const val TIINGO_API_KEY = "YOUR_TIINGO_API_KEY_HERE" // FIXME: Use secure method!

    }

    @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID)
    private val lastTimestampSpec: StateSpec<ValueState<Timestamp>> =
        StateSpecs.value(ProtoCoder.of(Timestamp::class.java))

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId(LAST_FETCHED_TIMESTAMP_STATE_ID) lastTimestampState: ValueState<Timestamp>
    ) {
        val currencyPair = context.element().key // e.g., "BTC/USD"
        val ticker = currencyPair.replace("/", "").toLowerCase() // e.g., "btcusd"

        logger.atInfo().log("Fetching Tiingo data for: %s (ticker: %s)", currencyPair, ticker)

        // Determine the start date for the API call
        val lastTimestamp = lastTimestampState.read()
        val startDate = if (lastTimestamp != null && lastTimestamp.seconds > 0) {
            // Start from the day *after* the last fetched candle
            val lastInstant = Instant.ofEpochSecond(lastTimestamp.seconds, lastTimestamp.nanos.toLong())
            val nextDay = LocalDate.ofInstant(lastInstant, ZoneOffset.UTC).plusDays(1)
            nextDay.format(TIINGO_DATE_FORMATTER)
        } else {
            logger.atInfo().log("No previous state found for %s. Using default start date: %s", currencyPair, DEFAULT_START_DATE)
            DEFAULT_START_DATE
        }

        // Construct API URL
        // Fetching daily ('1day') candles for simplicity. Adjust 'resampleFreq' as needed (e.g., '1min', '5min', '1hour')
        // Note: Intraday requires higher Tiingo subscription tiers.
        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=1day&token=$TIINGO_API_KEY" // Daily candles
        // val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=1min&token=$TIINGO_API_KEY" // 1-minute candles

        logger.atFine().log("Requesting URL: %s", url)

        var latestCandleTimestamp: Timestamp? = null

        try {
            val response = httpClient.get(url, emptyMap()) // Assuming GET request, add headers if needed
            logger.atFine().log("Received response for %s (length: %d)", currencyPair, response.length)

            val candles = TiingoResponseParser.parseCandles(response, currencyPair)

            if (candles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s", candles.size, currencyPair)
                candles.forEach { candle ->
                    context.output(candle)
                    // Track the latest timestamp encountered in this batch
                    if (latestCandleTimestamp == null || Timestamps.compare(candle.timestamp, latestCandleTimestamp!!) > 0) {
                        latestCandleTimestamp = candle.timestamp
                    }
                }
            } else {
                logger.atInfo().log("No new candle data returned for %s starting from %s", currencyPair, startDate)
            }

        } catch (e: IOException) {
            logger.atSevere().withCause(e).log("Failed to fetch or parse Tiingo data for %s from URL: %s", currencyPair, url)
            // Handle error appropriately (e.g., retry, dead-letter queue)
            return // Exit processing for this element on error
        }

        // Update state with the timestamp of the latest candle processed in this batch
        if (latestCandleTimestamp != null) {
            lastTimestampState.write(latestCandleTimestamp)
            logger.atInfo().log("Updated last timestamp state for %s to: %s", currencyPair, Timestamps.toString(latestCandleTimestamp))
        } else if (lastTimestamp == null) {
            // If we fetched initially and got no data, still write a timestamp
            // to avoid refetching from the default start date constantly.
            // Use the start date we queried from (or yesterday if start date was today).
            try {
                val startInstant = LocalDate.parse(startDate, TIINGO_DATE_FORMATTER).atStartOfDay().toInstant(ZoneOffset.UTC)
                val initialTimestamp = Timestamps.fromMillis(startInstant.toEpochMilli())
                lastTimestampState.write(initialTimestamp)
                 logger.atInfo().log("Initial fetch for %s yielded no data. Setting last timestamp state to start date: %s", currencyPair, Timestamps.toString(initialTimestamp))
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log("Could not parse start date '%s' to set initial state for %s", startDate, currencyPair)
            }
        }
    }
}
