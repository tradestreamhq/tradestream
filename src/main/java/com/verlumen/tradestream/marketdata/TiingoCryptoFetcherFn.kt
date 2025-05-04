package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.time.format.DateTimeFormatter

// NOTE: This is a basic implementation. State and AssistedInject will be added later.

/**
 * A basic DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 * This version does *not* yet include state management or fill-forward logic.
 */
class TiingoCryptoFetcherFn @Inject constructor( // Temporarily use @Inject for HttpClient
    private val httpClient: HttpClient,
    // Temporary direct constructor args for config (will become @Assisted)
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void>, KV<String, Candle>>() { // Input KV<PairSymbol, Void>, Output KV<PairSymbol, Candle>

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ISO_LOCAL_DATE // yyyy-MM-dd for daily
        // private val TIINGO_DATE_FORMATTER_INTRADAY = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss") // Not needed yet

        private const val DEFAULT_START_DATE = "2019-01-02" // Always fetch from start for now
        private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

        // --- Helper Methods ---
        /**
         * Converts a Joda Duration to a Tiingo resampleFreq parameter string.
         */
        fun durationToResampleFreq(duration: Duration): String {
            return when {
                duration.getStandardDays() >= 1 -> "${duration.getStandardDays()}day"
                duration.getStandardHours() >= 1 -> "${duration.getStandardHours()}hour"
                duration.getStandardMinutes() > 0 -> "${duration.getStandardMinutes()}min"
                else -> "1min" // Default to 1min if duration is too small or zero
            }
        }

        /**
         * Determines if the granularity is daily or intraday based on Joda Duration.
         */
        fun isDailyGranularity(duration: Duration): Boolean {
            return duration.isLongerThan(Duration.standardHours(23)) // Consider >= 1 day as daily
        }
        // --- End Helper Methods ---
    }

    @ProcessElement
    fun processElement(context: ProcessContext) {
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").toLowerCase()
        val resampleFreq = durationToResampleFreq(granularity)

         // Basic API Key validation
        if (apiKey.isBlank() || apiKey == "YOUR_TIINGO_API_KEY_HERE") {
             logger.atWarning().log("Tiingo API Key is missing or using placeholder for %s. Skipping fetch.", currencyPair)
             return // Skip processing if key is invalid
        }


        logger.atInfo().log("Fetching Tiingo data for: %s (ticker: %s) with granularity: %s",
            currencyPair, ticker, resampleFreq)

        // Use DEFAULT_START_DATE for this PR (stateful logic comes later)
        val startDate = DEFAULT_START_DATE

        // Construct API URL
        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=$resampleFreq&token=$apiKey"
        logger.atFine().log("Requesting URL: %s", url)

        try {
            val response = httpClient.get(url, emptyMap()) // Assuming GET request
            logger.atFine().log("Received response for %s (length: %d)", currencyPair, response.length)

            val fetchedCandles = TiingoResponseParser.parseCandles(response, currencyPair)

            if (fetchedCandles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s with granularity %s",
                    fetchedCandles.size, currencyPair, resampleFreq)

                fetchedCandles.forEach { candle ->
                    // Output KV pair
                    context.output(KV.of(currencyPair, candle))
                }
            } else {
                logger.atInfo().log("No candle data returned from Tiingo for %s starting %s",
                    currencyPair, startDate)
            }
        } catch (e: IOException) {
            logger.atSevere().withCause(e).log("Failed to fetch or parse Tiingo data for %s from URL: %s",
                currencyPair, url)
            // Basic error handling for now
        } catch (e: Exception) {
             logger.atSevere().withCause(e).log("Unexpected error fetching Tiingo data for %s from URL: %s",
                currencyPair, url)
        }
    }
}
