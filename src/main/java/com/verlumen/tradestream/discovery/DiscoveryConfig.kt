package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.verlumen.tradestream.execution.RunMode
import com.verlumen.tradestream.sql.DataSourceConfig

data class DiscoveryConfig
    @Inject
    constructor(
        val dataSourceConfig: DataSourceConfig,
        val runMode: RunMode,
    )
