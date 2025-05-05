package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.ProcessContext
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.values.KV
import org.joda.time.Duration
import java.io.IOException
import java.io.Serializable
import java.time.format.DateTimeFormatter

/**
 * A basic DoFn to fetch cryptocurrency candle data from the Tiingo API for a specific currency pair.
 * State and AssistedInject will be added later.
 */
class TiingoCryptoFetcherFn @Inject constructor(
    private val httpClient: HttpClient,
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val TIINGO_DATE_FORMATTER_DAILY = DateTimeFormatter.ISO_LOCAL_DATE
        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL = "https://api.tiingo.com/tiingo/crypto/prices"

        /** Convert a Joda Duration into Tiingo’s `resampleFreq` string. */
        fun durationToResampleFreq(duration: Duration): String {
            return when {
                duration.standardDays >= 1   -> "${duration.standardDays}day"
                duration.standardHours >= 1  -> "${duration.standardHours}hour"
                duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
                else                         -> "1min"
            }
        }
    }

    @ProcessElement
    fun processElement(ctx: ProcessContext) {
        val currencyPair = ctx.element().key

        if (apiKey.isBlank() || apiKey == "YOUR_TIINGO_API_KEY_HERE") {
            logger.atWarning()
                .log("Tiingo API Key is missing or placeholder for %s. Skipping fetch.", currencyPair)
            return
        }

        val ticker       = currencyPair.replace("/", "").lowercase()
        val resampleFreq = durationToResampleFreq(granularity)
        val url = "$TIINGO_API_URL?tickers=$ticker" +
                  "&startDate=$DEFAULT_START_DATE" +
                  "&resampleFreq=$resampleFreq" +
                  "&token=$apiKey"

        logger.atInfo()
            .log("Fetching Tiingo data for %s (ticker=%s, freq=%s)", currencyPair, ticker, resampleFreq)
        logger.atFine().log("Request URL: %s", url)

        try {
            val response = httpClient.get(url, emptyMap())
            val candles  = TiingoResponseParser.parseCandles(response, currencyPair)

            if (candles.isNotEmpty()) {
                logger.atInfo().log("Parsed %d candles for %s", candles.size, currencyPair)
                candles.forEach { ctx.output(KV.of(currencyPair, it)) }
            } else {
                logger.atInfo()
                    .log("No candle data from Tiingo for %s starting %s", currencyPair, DEFAULT_START_DATE)
            }

        } catch (e: IOException) {
            logger.atSevere().withCause(e)
                .log("I/O error fetching/parsing Tiingo data for %s: %s", currencyPair, e.message)
        } catch (e: Exception) {
            logger.atSevere().withCause(e)
                .log("Unexpected error fetching Tiingo data for %s: %s", currencyPair, e.message)
        }
    }
}
