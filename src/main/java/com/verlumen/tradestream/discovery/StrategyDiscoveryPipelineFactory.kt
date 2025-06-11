package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.Singleton
import com.verlumen.tradestream.sql.DataSourceConfig

/**
 * Factory for creating StrategyDiscoveryPipeline instances with configuration.
 */
interface StrategyDiscoveryPipelineFactory {
    /**
     * Creates a new StrategyDiscoveryPipeline with the given options.
     */
    fun create(options: StrategyDiscoveryPipelineOptions): StrategyDiscoveryPipeline
}

/**
 * Implementation of StrategyDiscoveryPipelineFactory that uses Guice-injected dependencies.
 */
@Singleton
class StrategyDiscoveryPipelineFactoryImpl
    @Inject
    constructor(
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val writeFnFactory: WriteDiscoveredStrategiesToPostgresFnFactory,
        private val discoveryRequestSourceFactory: DiscoveryRequestSourceFactory,
    ) : StrategyDiscoveryPipelineFactory {
        override fun create(options: StrategyDiscoveryPipelineOptions): StrategyDiscoveryPipeline {
            val username = requireNotNull(options.databaseUsername) { "Database username is required." }
            val password = requireNotNull(options.databasePassword) { "Database password is required." }

            val dataSourceConfig =
                DataSourceConfig(
                    serverName = options.dbServerName,
                    databaseName = options.dbDatabaseName,
                    username = username,
                    password = password,
                    portNumber = options.dbPortNumber,
                    applicationName = null,
                    connectTimeout = null,
                    socketTimeout = null,
                    readOnly = null,
                )
            val writeFn = writeFnFactory.create(dataSourceConfig)

            // Create the discovery request source configured with pipeline options
            val discoveryRequestSource = discoveryRequestSourceFactory.create(options)

            return StrategyDiscoveryPipeline(
                discoveryRequestSource = discoveryRequestSource,
                runGAFn = runGAFn,
                extractFn = extractFn,
                writeFn = writeFn,
            )
        }
    }
