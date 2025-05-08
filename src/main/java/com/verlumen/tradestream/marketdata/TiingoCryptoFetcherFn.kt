// src/main/java/com/verlumen/tradestream/marketdata/TiingoCryptoFetcherFn.kt

package com.verlumen.tradestream.marketdata

import com.verlumen.tradestream.http.HttpClient
import com.google.common.flogger.FluentLogger
import com.google.protobuf.util.Timestamps
import com.google.protobuf.Timestamp
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
import javax.inject.Inject

class TiingoCryptoFetcherFn @Inject constructor(
    private val httpClient: HttpClient,
    private val granularity: Duration,
    private val apiKey: String
) : DoFn<KV<String, Void?>, KV<String, Candle>>() {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()

        private val TIINGO_DATE_FORMATTER_DAILY =
            DateTimeFormatter.ofPattern("yyyy-MM-dd")
        private val TIINGO_DATE_FORMATTER_INTRADAY =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

        private const val DEFAULT_START_DATE = "2019-01-02"
        private const val TIINGO_API_URL =
            "https://api.tiingo.com/tiingo/crypto/prices"

        fun durationToResampleFreq(duration: Duration): String {
            return when {
                duration.standardDays >= 1   -> "${duration.standardDays}day"
                duration.standardHours >= 1  -> "${duration.standardHours}hour"
                duration.standardMinutes > 0 -> "${duration.standardMinutes}min"
                else                         -> "1min"
            }
        }

        fun isDailyGranularity(duration: Duration): Boolean =
            duration.standardDays >= 1

        fun durationToTemporalUnit(duration: Duration): ChronoUnit =
            when {
                duration.standardDays >= 1  -> ChronoUnit.DAYS
                duration.standardHours >= 1 -> ChronoUnit.HOURS
                else                        -> ChronoUnit.MINUTES
            }

        fun durationToAmount(duration: Duration): Long =
            when {
                duration.standardDays >= 1  -> duration.standardDays
                duration.standardHours >= 1 -> duration.standardHours
                else                        -> duration.standardMinutes
            }
    }

    class StateTimestamp(val timestamp: Long) : Serializable {
        companion object {
            private const val serialVersionUID = 1L
            fun fromProtobufTimestamp(proto: Timestamp) =
                StateTimestamp(Timestamps.toMillis(proto))
        }
        constructor() : this(0L)
        override fun toString() = "StateTimestamp[$timestamp]"
    }

    @StateId("lastFetchedTimestamp")
    internal val lastTimestampSpec: StateSpec<ValueState<StateTimestamp>> =
        StateSpecs.value(SerializableCoder.of(StateTimestamp::class.java))

    @StateId("lastCandle")
    internal val lastCandleSpec: StateSpec<ValueState<Candle>> =
        StateSpecs.value(ProtoCoder.of(Candle::class.java))

    @ProcessElement
    fun processElement(
        context: DoFn<KV<String, Void?>, KV<String, Candle>>.ProcessContext,
        @StateId("lastFetchedTimestamp") lastTimestampState: ValueState<StateTimestamp>,
        @StateId("lastCandle") lastCandleState: ValueState<Candle>
    ) {
        val currencyPair = context.element().key
        val ticker = currencyPair.replace("/", "").lowercase()

        if (apiKey.isBlank()) {
            logger.atWarning().log(
              "Skipping Tiingo fetch for %s: Empty API key",
              currencyPair
            )
            return
        }

        val resampleFreq = durationToResampleFreq(granularity)
        logger.atInfo().log(
          "Processing fetch for: %s (ticker: %s, freq: %s)",
          currencyPair, ticker, resampleFreq
        )

        // Determine start date
        val lastState = lastTimestampState.read()
        val startDate = if (lastState != null && lastState.timestamp > 0) {
            val inst = Instant.ofEpochMilli(lastState.timestamp)
            if (isDailyGranularity(granularity)) {
                LocalDate.ofInstant(inst, ZoneOffset.UTC)
                    .plusDays(1)
                    .format(TIINGO_DATE_FORMATTER_DAILY)
            } else {
                LocalDateTime.ofInstant(inst, ZoneOffset.UTC)
                    .format(TIINGO_DATE_FORMATTER_INTRADAY)
            }
        } else {
            DEFAULT_START_DATE
        }

        val url = "$TIINGO_API_URL?tickers=$ticker" +
                  "&startDate=$startDate" +
                  "&resampleFreq=$resampleFreq" +
                  "&token=$apiKey"
        logger.atFine().log("Requesting URL: %s", url)

        var latestEpochMillis = 0L
        var currentLast = lastCandleState.read()

        try {
            val resp = httpClient.get(url, emptyMap())
            val fetched = TiingoResponseParser.parseCandles(resp, currencyPair)

            if (fetched.isNotEmpty()) {
                logger.atInfo().log(
                  "Parsed %d candles for %s",
                  fetched.size, currencyPair
                )

                val toEmit = fillMissingCandles(fetched, currentLast)
                for (c in toEmit) {
                    context.output(KV.of(currencyPair, c))
                    currentLast = c

                    // Only update if it's a real candle
                    if (fetched.any { it.timestamp == c.timestamp && it.volume > 0.0 }) {
                        val m = c.timestamp.seconds * 1000 +
                                c.timestamp.nanos / 1_000_000
                        if (m > latestEpochMillis) latestEpochMillis = m
                    }
                }
            } else {
                logger.atInfo().log(
                  "No new candle data from Tiingo for %s starting %s",
                  currencyPair, startDate
                )
                // Fill forward if we have previous candle
                if (currentLast != null) {
                    val now = Instant.now()
                    val unit = durationToTemporalUnit(granularity)
                    val amt = durationToAmount(granularity)
                    var next = Instant.ofEpochSecond(
                        currentLast.timestamp.seconds,
                        currentLast.timestamp.nanos.toLong()
                    ).plus(amt, unit)

                    val fills = mutableListOf<Candle>()
                    while (next.isBefore(now)) {
                        logger.atFine().log(
                          "API returned no data, filling forward for %s at %s",
                          currencyPair, next
                        )
                        val synth = createSyntheticCandle(
                            currentLast, currencyPair, next
                        )
                        fills.add(synth)
                        currentLast = synth
                        next = next.plus(amt, unit)
                    }
                    fills.forEach { context.output(KV.of(currencyPair, it)) }
                }
            }
        } catch (io: IOException) {
            logger.atWarning().withCause(io)
                  .log("Error fetching data from Tiingo for %s", currencyPair)
            return
        } catch (ex: Exception) {
            logger.atSevere().withCause(ex)
                  .log("Unexpected error processing %s", currencyPair)
            return
        }

        // Update timestamp state
        if (latestEpochMillis > 0) {
            val existing = lastTimestampState.read()
            if (existing == null || existing.timestamp < latestEpochMillis) {
                lastTimestampState.write(StateTimestamp(latestEpochMillis))
                logger.atInfo().log(
                  "Updated last timestamp state for %s to: %d",
                  currencyPair, latestEpochMillis
                )
            }
        } else if (lastTimestampState.read() == null) {
            try {
                val initMillis = if (isDailyGranularity(granularity)) {
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
                  "Initialized state for %s with start date: %s",
                  currencyPair, startDate
                )
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log(
                  "Could not parse start date '%s' to set initial state for %s",
                  startDate, currencyPair
                )
            }
        }

        // Update lastCandle state
        if (currentLast != null) {
            lastCandleState.write(currentLast)
            logger.atFine().log(
              "Updated last emitted candle state for %s to candle at: %s",
              currencyPair,
              Timestamps.toString(currentLast.timestamp)
            )
        }
    }

    private fun fillMissingCandles(
        fetched: List<Candle>,
        lastKnown: Candle?
    ): List<Candle> {
        // If there's no prior candle, just emit exactly what we fetched
        if (lastKnown == null) return fetched
        if (fetched.isEmpty()) return emptyList()

        val unit = durationToTemporalUnit(granularity)
        val amount = durationToAmount(granularity)
        val out = mutableListOf<Candle>()
        var prev = lastKnown

        for (c in fetched) {
            val currTime = Instant.ofEpochSecond(
                c.timestamp.seconds,
                c.timestamp.nanos.toLong()
            )
            var nextExpected = Instant.ofEpochSecond(
                prev.timestamp.seconds,
                prev.timestamp.nanos.toLong()
            ).plus(amount, unit)

            while (nextExpected.isBefore(currTime)) {
                logger.atFine().log(
                  "Filling gap for %s at %s (before %s)",
                  c.currencyPair, nextExpected, currTime
                )
                val synth = createSyntheticCandle(prev, c.currencyPair, nextExpected)
                out.add(synth)
                prev = synth
                nextExpected = nextExpected.plus(amount, unit)
            }
            out.add(c)
            prev = c
        }
        return out
    }

    private fun createSyntheticCandle(
        reference: Candle,
        currencyPair: String,
        timestamp: Instant
    ): Candle {
        val tsProto = Timestamps.fromMillis(timestamp.toEpochMilli())
        val price = reference.close
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
