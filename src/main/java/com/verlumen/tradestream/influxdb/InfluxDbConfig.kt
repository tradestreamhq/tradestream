package com.verlumen.tradestream.influxdb

data class InfluxDbConfig(
    private val url: String,
    private val token: String,
    private val org: String,
    private val bucket: String,
)
