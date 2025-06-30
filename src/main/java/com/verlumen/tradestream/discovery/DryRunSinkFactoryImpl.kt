package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.verlumen.tradestream.sql.DataSourceConfig

class DryRunSinkFactoryImpl
    @Inject
    constructor(
        private val dryRunDiscoveredStrategySinkFactory: DryRunDiscoveredStrategySinkFactory,
    ) : DiscoveredStrategySinkFactory {
        override fun create(params: DiscoveredStrategySinkParams): DiscoveredStrategySink {
            // We know it's DryRun, so create dummy config
            val dummyConfig =
                DataSourceConfig(
                    serverName = "dummy",
                    databaseName = "dummy",
                    username = "dummy",
                    password = "dummy",
                    portNumber = 5432,
                    applicationName = "dry-run",
                    connectTimeout = 30,
                    socketTimeout = 60,
                    readOnly = false,
                )
            return dryRunDiscoveredStrategySinkFactory.create(dummyConfig)
        }
    } 