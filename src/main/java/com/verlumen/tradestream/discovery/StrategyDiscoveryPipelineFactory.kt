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
        private val discoveryRequestSourceFactory: DiscoveryRequestSourceFactory,
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val writeFnFactory: WriteDiscoveredStrategiesToPostgresFnFactory,
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
                    // Pass null for other optional params for now as they are not in options
                    applicationName = null,
                    connectTimeout = null,
                    socketTimeout = null,
                    readOnly = null,
                )
            val writeFn = writeFnFactory.create(dataSourceConfig)

            // Create the discovery request source configured with pipeline options
            val discoveryRequestSource = discoveryRequestSourceFactory.create(options)

            return StrategyDiscoveryPipeline(
                isStreaming = true,
                discoveryRequestSource = discoveryRequestSource,
                runGAFn = runGAFn,
                extractFn = extractFn,
                writeFn = writeFn,
            )
        }
    }
