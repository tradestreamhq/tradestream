package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.Singleton

/**
 * Implementation of DiscoveredStrategySinkFactory that creates sinks based on sealed class parameters.
 *
 * This factory directly creates the appropriate sink implementation based on the parameter type,
 * providing a unified interface for all sink types.
 */
@Singleton
class DiscoveredStrategySinkFactoryImpl
    @Inject
    constructor(
        private val strategyRepositoryFactory: StrategyRepository.Factory,
    ) : DiscoveredStrategySinkFactory {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }

        override fun create(params: DiscoveredStrategySinkParams): DiscoveredStrategySink =
            when (params) {
                is DiscoveredStrategySinkParams.Postgres -> {
                    logger.atInfo().log("Creating PostgreSQL sink")
                    WriteDiscoveredStrategiesToPostgresFn(strategyRepositoryFactory, params.config)
                }
                is DiscoveredStrategySinkParams.Kafka -> {
                    logger.atInfo().log("Creating Kafka sink for topic: %s", params.topic)
                    WriteDiscoveredStrategiesToKafkaFn(params.bootstrapServers, params.topic)
                }
                is DiscoveredStrategySinkParams.DryRun -> {
                    logger.atInfo().log("Creating dry-run sink")
                    // For dry-run, we need a dummy config since the interface requires it
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
