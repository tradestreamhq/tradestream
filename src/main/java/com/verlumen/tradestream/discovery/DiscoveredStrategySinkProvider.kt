package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.Provider
import com.verlumen.tradestream.execution.RunMode

class DiscoveredStrategySinkProvider
    @Inject
    constructor(
        private val config: DiscoveryConfig,
    ) : Provider<DiscoveredStrategySink> {
        override fun get(): DiscoveredStrategySink =
            when (config.runMode) {
                RunMode.DRY -> NoOpDiscoveredStrategySink()
                RunMode.WET -> PostgresDiscoveredStrategySink(config.dataSourceConfig)
            }
    } 
