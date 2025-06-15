package com.verlumen.tradestream.influxdb

import com.influxdb.client.InfluxDBClient
import com.influxdb.client.InfluxDBClientFactory
import java.io.Serializable

interface InfluxDbClientFactory {
    fun create(config: InfluxDbConfig): InfluxDBClient
}

class InfluxDbClientFactoryImpl : InfluxDbClientFactory, Serializable {
    override fun create(config: InfluxDbConfig): InfluxDBClient =
        com.influxdb.client.InfluxDBClientFactory.create(
            config.url,
            config.token.toCharArray(),
            config.org,
            config.bucket,
        )
    
    companion object {
        private const val serialVersionUID: Long = 1L
    }
}
