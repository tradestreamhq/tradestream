package com.verlumen.tradestream.influxdb

data class InfluxDbConfig(
    val url: String,
    val token: String,
    val org: String,
    val bucket: String,
)
