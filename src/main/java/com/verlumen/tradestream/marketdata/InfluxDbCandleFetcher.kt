package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.Provider
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.influxdb.InfluxDbClientFactory
import com.verlumen.tradestream.influxdb.InfluxDbConfig
import com.influxdb.client.InfluxDBClient
import java.io.Serializable

/**
 * Fetches candle data from an InfluxDB instance using the Java client.
 */
class InfluxDbCandleFetcher
    @Inject
    constructor(
        private val influxDbClientFactory: InfluxDbClientFactory,
        @Assisted private val influxDbConfig: InfluxDbConfig,
    ) : CandleFetcher, Serializable {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID = 1L
        }

        override fun fetchCandles(
            symbol: String,
            startTime: Timestamp,
            endTime: Timestamp,
        ): ImmutableList<Candle> {
            val startIso = Timestamps.toString(startTime)
            val endIso = Timestamps.toString(endTime)
            val fluxQuery = buildFluxQuery(symbol, startIso, endIso)
            logger.atInfo().log("Executing Flux query for %s: %s", symbol, fluxQuery)

            return executeQueryWithClient(fluxQuery, symbol, startIso, endIso)
        }

        private fun executeQueryWithClient(
            fluxQuery: String,
            symbol: String,
            startIso: String,
            endIso: String,
        ): ImmutableList<Candle> {
            return influxDbClientFactory.create(influxDbConfig).use { influxDBClient ->
                val queryApi = influxDBClient.queryApi
                val candlesBuilder = ImmutableList.builder<Candle>()

                try {
                    val tables = queryApi.query(fluxQuery, influxDbConfig.org)
                    for (table in tables) {
                        for (record in table.records) {
                            try {
                                val candle = parseCandle(record, symbol)
                                if (candle != null) {
                                    candlesBuilder.add(candle)
                                }
                            } catch (e: Exception) {
                                logger.atWarning().withCause(e).log(
                                    "Failed to parse FluxRecord into Candle for symbol %s. Record: %s",
                                    symbol,
                                    record.values,
                                )
                            }
                        }
                    }
                } catch (e: Exception) {
                    logger.atSevere().withCause(e).log("Error fetching candles from InfluxDB for %s", symbol)
                    // Consider re-throwing a custom exception or returning an empty list with error state
                }

                val result = candlesBuilder.build()
                logger.atInfo().log("Fetched %d candles for symbol %s from %s to %s", result.size, symbol, startIso, endIso)
                result
            }
        }

        private fun buildFluxQuery(
            symbol: String,
            startIso: String,
            endIso: String,
        ): String =
            """
            from(bucket: "${influxDbConfig.bucket}")
              |> range(start: $startIso, stop: $endIso)
              |> filter(fn: (r) => r._measurement == "candles")
              |> filter(fn: (r) => r.currency_pair == "$symbol")
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> sort(columns: ["_time"])
            """.trimIndent()

        private fun parseCandle(
            record: com.influxdb.query.FluxRecord,
            symbol: String,
        ): Candle? {
            val time = record.time
            if (time == null) {
                logger.atWarning().log("Skipping record with null time for symbol %s", symbol)
                return null
            }
            val candleTimestamp = Timestamps.fromMillis(time.toEpochMilli())

            return Candle
                .newBuilder()
                .setTimestamp(candleTimestamp)
                .setCurrencyPair(symbol)
                .setOpen((record.getValueByKey("open") as Number).toDouble())
                .setHigh((record.getValueByKey("high") as Number).toDouble())
                .setLow((record.getValueByKey("low") as Number).toDouble())
                .setClose((record.getValueByKey("close") as Number).toDouble())
                .setVolume((record.getValueByKey("volume") as Number).toDouble())
                .build()
        }

        override fun close() {
            // No need to manage client lifecycle manually anymore since we're using try-with-resources
            logger.atInfo().log("InfluxDbCandleFetcher closed.")
        }
    }
