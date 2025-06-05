package com.verlumen.tradestream.influxdb

import com.google.inject.AbstractModule
import com.google.inject.Provider
import com.influxdb.client.InfluxDBClient
import com.influxdb.client.InfluxDBClientFactory
import java.io.Serializable

internal class InfluxDBClientProvider(
    private val influxDbUrl: String,
    private val influxDbToken: String,
    private val influxDbOrg: String,
    private val influxDbBucket: String,
) : Provider<InfluxDBClient>, Serializable {
    
    override fun get(): InfluxDBClient =
        InfluxDBClientFactory.create(
            influxDbUrl,
            influxDbToken.toCharArray(),
            influxDbOrg,
            influxDbBucket,
        )
}

class InfluxDbModule(
    private val influxDbUrl: String,
    private val influxDbToken: String,
    private val influxDbOrg: String,
    private val influxDbBucket: String,
) : AbstractModule() {
    
    override fun configure() {
        bind(InfluxDBClient::class.java)
            .toProvider(
                InfluxDBClientProvider(
                    influxDbUrl,
                    influxDbToken,
                    influxDbOrg,
                    influxDbBucket
                )
            )
    }
}
