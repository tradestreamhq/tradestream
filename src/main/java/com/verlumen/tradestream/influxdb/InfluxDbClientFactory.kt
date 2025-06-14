package com.verlumen.tradestream.influxdb

import com.influxdb.client.InfluxDBClient
import com.influxdb.client.InfluxDBClientFactory

interface InfluxDbClientFactory {
    fun create(config: InfluxDbConfig): InfluxDBClient
}

class InfluxDbClientFactoryImpl : InfluxDbClientFactory {
    override fun create(config: InfluxDbConfig): InfluxDBClient =
        com.influxdb.client.InfluxDBClientFactory.create(
            config.url,
            config.token.toCharArray(),
            config.org,
            config.bucket,
        )
}
