package com.verlumen.tradestream.marketdata

import com.google.inject.AbstractModule
import com.google.inject.Provides
import com.google.inject.Singleton
import com.influxdb.client.InfluxDBClient
import com.influxdb.client.InfluxDBClientFactory

class InfluxDbModule(
    private val influxDbUrl: String,
    private val influxDbToken: String,
    private val influxDbOrg: String,
    private val influxDbBucket: String
) : AbstractModule() {
    @Provides
    @Singleton
    fun provideInfluxDBClient(): InfluxDBClient =
        InfluxDBClientFactory.create(
            influxDbUrl,
            influxDbToken.toCharArray(),
            influxDbOrg,
            influxDbBucket,
        )
}
