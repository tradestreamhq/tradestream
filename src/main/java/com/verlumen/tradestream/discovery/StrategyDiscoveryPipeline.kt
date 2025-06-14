package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.influxdb.InfluxDbConfig
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher
import com.verlumen.tradestream.sql.DataSourceConfig
import org.apache.beam.sdk.Pipeline
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
        private val runGADiscoveryFnFactory: RunGADiscoveryFnFactory,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val writeFnFactory: WriteDiscoveredStrategiesToPostgresFnFactory,
        private val discoveryRequestSourceFactory: DiscoveryRequestSourceFactory,
        private val candleFetcherFactory: InfluxDbCandleFetcher.Factory,
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

            val influxDbConfig =
                InfluxDbConfig(
                    url = options.influxDbUrl,
                    token = requireNotNull(options.influxDbToken) { "InfluxDB token is required." },
                    org = options.influxDbOrg,
                    bucket = options.influxDbBucket,
                )
            val candleFetcher = candleFetcherFactory.create(influxDbConfig)
            val discoveryRequestSource = discoveryRequestSourceFactory.create(options)
            val runGaFn = runGADiscoveryFnFactory.create(candleFetcher)
            val writeFn = writeFnFactory.create(dataSourceConfig)

            val pipeline = Pipeline.create(options)

            pipeline
                .apply("ReadDiscoveryRequests", discoveryRequestSource)
                .apply("RunGAStrategyDiscovery", ParDo.of(runGaFn))
                .apply("ExtractStrategies", ParDo.of(extractFn))
                .apply("WriteToPostgreSQL", ParDo.of(writeFn))

            pipeline.run().waitUntilFinish()
        }

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }
    }
