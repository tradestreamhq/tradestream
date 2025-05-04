package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.Provider
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.ProcessContext
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StartBundle
import org.apache.beam.sdk.transforms.DoFn.Setup
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.time.format.DateTimeFormatter
import java.io.Serializable

// NOTE: This is a basic implementation. State and AssistedInject will be added later.

/**
 * A basic DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 * This version does *not* yet include state management or fill-forward logic.
 */
class TiingoCryptoFetcherFn @Inject constructor(
    private val httpClientProvider: Provider<HttpClient>, // Inject Provider
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void>, KV<String, Candle>>(), Serializable { // Ensure DoFn implements Serializable

    @Transient
    private var httpClient: HttpClient? = null
    
    @Setup
    fun setup() {
        try {
            httpClient = httpClientProvider.get()
            logger.atInfo().log("HttpClient initialized in Setup")
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Failed to initialize HttpClient in Setup")
        }
    }
    
    @StartBundle
    fun startBundle() {
        try {
            if (httpClient == null) {
                httpClient = httpClientProvider.get()
                logger.atInfo().log("HttpClient initialized in StartBundle")
            }
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Failed to initialize HttpClient in StartBundle")
        }
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ISO_LOCAL_DATE // yyyy-MM-dd for daily
        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

        /** Converts a Joda Duration to a Tiingo resampleFreq parameter string. */
        fun durationToResampleFreq(duration: Duration): String {
            return when {
                duration.standardDays >= 1 -> "${duration.standardDays}day"
                duration.standardHours >= 1 -> "${duration.standardHours}hour"
                duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
                else -> "1min"
            }
        }

        /** Determines if the granularity is daily or intraday based on Joda Duration. */
        fun isDailyGranularity(duration: Duration): Boolean =
            duration.isLongerThan(Duration.standardHours(23))
    }

    @ProcessElement
    fun processElement(context: ProcessContext) {
        // Last resort: try to get a client if still null
        if (httpClient == null) {
            try {
                httpClient = httpClientProvider.get()
                logger.atInfo().log("HttpClient initialized in ProcessElement")
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Failed to initialize HttpClient in ProcessElement")
                // Continue with null client and let it fail with clear error message
            }
        }
        
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").lowercase()
        val resampleFreq = durationToResampleFreq(granularity)

        if (apiKey.isBlank() || apiKey == "YOUR_TIINGO_API_KEY_HERE") {
            logger.atWarning()
                .log("Tiingo API Key is missing or placeholder for %s. Skipping fetch.", currencyPair)
            return
        }

        logger.atInfo()
            .log("Fetching Tiingo data for: %s (ticker: %s) with granularity: %s",
                 currencyPair, ticker, resampleFreq)

        val startDate = DEFAULT_START_DATE
        val url = "$TIINGO_API_URL?tickers=$ticker&startDate=$startDate&resampleFreq=$resampleFreq&token=$apiKey"
        logger.atFine().log("Requesting URL: %s", url)

        try {
            if (httpClient == null) {
                throw IllegalStateException("HttpClient is null, cannot fetch data")
            }
            
            val response = httpClient!!.get(url, emptyMap())
            val fetchedCandles = TiingoResponseParser.parseCandles(response, currencyPair)

            if (fetchedCandles.isNotEmpty()) {
                logger.atInfo()
                    .log("Parsed %d candles for %s with granularity %s",
                         fetchedCandles.size, currencyPair, resampleFreq)
                fetchedCandles.forEach { candle ->
                    context.output(KV.of(currencyPair, candle))
                }
            } else {
                logger.atInfo()
                    .log("No candle data returned from Tiingo for %s starting %s",
                         currencyPair, startDate)
            }
        } catch (e: IOException) {
            logger.atSevere().withCause(e)
                .log("Failed to fetch or parse Tiingo data for %s from URL: %s",
                     currencyPair, url)
        } catch (e: Exception) {
            logger.atSevere().withCause(e)
                .log("Unexpected error fetching Tiingo data for %s from URL: %s",
                     currencyPair, url)
        }
    }
}
