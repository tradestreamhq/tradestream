package com.verlumen.tradestream.influxdb

import kotlinx.serialization.Serializable

@Serializable
data class InfluxDbConfig(
    val url: String,
    val token: String,
    val org: String,
    val bucket: String,
)
