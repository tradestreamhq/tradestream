package com.verlumen.tradestream.influxdb

import com.google.inject.AbstractModule

class InfluxDbModule() : AbstractModule() {
    override fun configure() {
        bind(InfluxDbClientFactory::class.java).to(InfluxDbClientFactoryImpl::class.java)
    }
}
