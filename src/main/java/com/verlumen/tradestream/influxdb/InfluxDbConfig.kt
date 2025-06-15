package com.verlumen.tradestream.influxdb

import java.io.Serializable

data class InfluxDbConfig:Serializable(
    val url: String,
    val token: String,
    val org: String,
    val bucket: String,
)
