package com.verlumen.tradestream.discovery

import com.google.inject.Inject

class SinkResolver
    @Inject
    constructor(
        private val writeDiscoveredStrategiesToKafkaFactory: WriteDiscoveredStrategiesToKafkaFactory,
        private val strategyRepositoryFactory: StrategyRepository.Factory,
    ) {
        fun resolve(params: DiscoveredStrategySinkParams): DiscoveredStrategySink =
            when (params) {
                is DiscoveredStrategySinkParams.Postgres ->
                    WriteDiscoveredStrategiesToPostgresFn(strategyRepositoryFactory, params.config)
                is DiscoveredStrategySinkParams.Kafka ->
                    writeDiscoveredStrategiesToKafkaFactory.create(params.bootstrapServers, params.topic)
                is DiscoveredStrategySinkParams.DryRun -> {
                    val dummyConfig =
                        com.verlumen.tradestream.sql.DataSourceConfig(
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
                    DryRunDiscoveredStrategySink(dummyConfig)
                }
            }
    } 
