package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.influxdb.client.InfluxDBClientFactory
import com.influxdb.client.InfluxDBClient
import com.google.common.flogger.FluentLogger

/**
 * Fetches candle data from an InfluxDB instance.
 */
class InfluxDbCandleFetcher(
    url: String,
    token: String,
    private val org: String,
    private val bucket: String
) : CandleFetcher {
    private val influxDBClient: InfluxDBClient = InfluxDBClientFactory.create(url, token.toCharArray(), org, bucket)

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    init {
        logger.atInfo().log("InfluxDbCandleFetcher initialized for org: %s, bucket: %s", org, bucket)
    }

    override fun fetchCandles(symbol: String, startTime: Timestamp, endTime: Timestamp): ImmutableList<Candle> {
        val startIso = Timestamps.toString(startTime)
        val endIso = Timestamps.toString(endTime)
        val fluxSymbol = symbol // Adjust if your InfluxDB tag for currency_pair is different

        val fluxQuery = """
            from(bucket: "$bucket")
              |> range(start: $startIso, stop: $endIso)
              |> filter(fn: (r) => r._measurement == "candles")
              |> filter(fn: (r) => r.currency_pair == "$fluxSymbol")
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> sort(columns: ["_time"])
            """.trimIndent()

        logger.atInfo().log("Executing Flux query for %s: %s", symbol, fluxQuery)
        val queryApi = influxDBClient.queryApi
        val candlesBuilder = ImmutableList.builder<Candle>()

        try {
            val tables = queryApi.query(fluxQuery, org)
            for (table in tables) {
                for (record in table.records) {
                    try {
                        val time = record.time
                        if (time == null) {
                            logger.atWarning().log("Skipping record with null time for symbol %s", symbol)
                            continue
                        }
                        val candleTimestamp = Timestamps.fromMillis(time.toEpochMilli())

                        // Assuming Candle is a Protobuf message or a class with a similar builder pattern
                        val candle =
                            Candle
                                .newBuilder() // Ensure Candle and its newBuilder() are accessible
                                .setTimestamp(candleTimestamp)
                                .setCurrencyPair(symbol)
                                .setOpen((record.getValueByKey("open") as Number).toDouble())
                                .setHigh((record.getValueByKey("high") as Number).toDouble())
                                .setLow((record.getValueByKey("low") as Number).toDouble())
                                .setClose((record.getValueByKey("close") as Number).toDouble())
                                .setVolume((record.getValueByKey("volume") as Number).toDouble())
                                .build()
                        candlesBuilder.add(candle)
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

    override fun close() {
        influxDBClient.close()
        logger.atInfo().log("InfluxDbCandleFetcher closed.")
    }
}
