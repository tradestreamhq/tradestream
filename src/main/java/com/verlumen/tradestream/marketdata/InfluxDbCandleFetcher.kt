package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.common.flogger.FluentLogger
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.influxdb.client.InfluxDBClient
import com.influxdb.client.InfluxDBClientFactory

/**
 * Fetches candle data from an InfluxDB instance using the Java client.
 */
class InfluxDbCandleFetcher(
    url: String,
    token: String,
    private val org: String,
    private val bucket: String,
) : CandleFetcher {
    private val influxDBClient: InfluxDBClient = InfluxDBClientFactory.create(url, token.toCharArray(), org, bucket)

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    init {
        logger.atInfo().log("InfluxDbCandleFetcher initialized for org: %s, bucket: %s", org, bucket)
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
        val queryApi = influxDBClient.queryApi
        val candlesBuilder = ImmutableList.builder<Candle>()

        try {
            val tables = queryApi.query(fluxQuery, org)
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
        return result
    }

    private fun buildFluxQuery(symbol: String, startIso: String, endIso: String): String {
        return """
            from(bucket: "$bucket")
              |> range(start: $startIso, stop: $endIso)
              |> filter(fn: (r) => r._measurement == "candles")
              |> filter(fn: (r) => r.currency_pair == "$symbol")
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> sort(columns: ["_time"])
        """.trimIndent()
    }

    private fun parseCandle(record: com.influxdb.query.FluxRecord, symbol: String): Candle? {
        val time = record.time
        if (time == null) {
            logger.atWarning().log("Skipping record with null time for symbol %s", symbol)
            return null
        }
        
        val candleTimestamp = Timestamps.fromMillis(time.toEpochMilli())

        return Candle.newBuilder()
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
        influxDBClient.close()
        logger.atInfo().log("InfluxDbCandleFetcher closed.")
    }
}
