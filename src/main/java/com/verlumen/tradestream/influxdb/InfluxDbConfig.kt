package com.verlumen.tradestream.influxdb

import java.io.Serializable

data class InfluxDbConfig(
    val url: String,
    val token: String,
    val org: String,
    val bucket: String,
) : Serializable
