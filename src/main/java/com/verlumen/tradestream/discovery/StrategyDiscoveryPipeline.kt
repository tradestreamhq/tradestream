package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.verlumen.tradestream.sql.DataSourceConfig

import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.ParDo

/**
 * Builds and executes the strategy-discovery Beam pipeline.
 *
 * Flow:
 * 1. Read discovery requests from source (e.g., Kafka)
 * 2. Run GA optimization for each request
 * 3. Extract discovered strategies
 * 4. Persist strategies to PostgreSQL
 *
 * All transforms arrive through the factory pattern with Guice.
 */
class StrategyDiscoveryPipeline
    @Inject
    constructor(
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val writeFnFactory: WriteDiscoveredStrategiesToPostgresFnFactory,
        private val discoveryRequestSourceFactory: DiscoveryRequestSourceFactory,
    ) {
    fun run(options: StrategyDiscoveryPipelineOptions) {
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

        val discoveryRequestSource = discoveryRequestSourceFactory.create(options);
        val writeFn = writeFnFactory.create(dataSourceConfig)

        val pipeline = Pipeline.create(options)

        pipeline
            .apply("ReadDiscoveryRequests", discoveryRequestSource)
            .apply("RunGAStrategyDiscovery", ParDo.of(runGAFn))
            .apply("ExtractStrategies", ParDo.of(extractFn))
            .apply("WriteToPostgreSQL", ParDo.of(writeFn))

        pipeline.run().waitUntilFinish()
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }
}
