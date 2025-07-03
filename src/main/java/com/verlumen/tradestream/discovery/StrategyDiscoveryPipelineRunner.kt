package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Module
import com.google.inject.Provider
import com.verlumen.tradestream.backtesting.BacktestingModule
import com.verlumen.tradestream.influxdb.InfluxDbConfig
import com.verlumen.tradestream.influxdb.InfluxDbModule
import com.verlumen.tradestream.marketdata.CandleFetcher
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher
import com.verlumen.tradestream.marketdata.MarketDataModule
import com.verlumen.tradestream.postgres.PostgresModule
import com.verlumen.tradestream.ta4j.Ta4jModule
import org.apache.beam.runners.flink.FlinkPipelineOptions
import org.apache.beam.sdk.options.PipelineOptionsFactory

/**
 * Builds and executes the strategy-discovery Beam pipeline.
 *
 * Flow:
 * 1. Read discovery requests from Kafka
 * 2. Deserialize protobuf messages
 * 3. Run GA optimisation for each request
 * 4. Extract discovered strategies
 * 5. Persist strategies to PostgreSQL
 *
 * All DoFns arrive through the factory pattern with Guice.
 */
class StrategyDiscoveryPipelineRunner {
    /**
     * Factory class that uses dependency injection to create pipeline instances
     * and their dependencies based on configuration options.
     */
    class StrategyDiscoveryPipelineFactory
        @Inject
        constructor(
            private val pipelineProvider: Provider<StrategyDiscoveryPipeline>,
            private val dryRunCandleFetcherProvider: Provider<DryRunCandleFetcher>,
            private val influxDbCandleFetcherFactoryProvider: Provider<InfluxDbCandleFetcher.Factory>,
        ) {
            data class PipelineComponents(
                val pipeline: StrategyDiscoveryPipeline,
                val candleFetcher: CandleFetcher,
            )

            /**
             * Creates the pipeline and candle fetcher based on the provided options.
             */
            fun create(options: StrategyDiscoveryPipelineOptions): PipelineComponents {
                val pipeline = pipelineProvider.get()
                val candleFetcher = createCandleFetcher(options)

                return PipelineComponents(pipeline, candleFetcher)
            }

            private fun createCandleFetcher(options: StrategyDiscoveryPipelineOptions): CandleFetcher {
                if (options.dryRun) {
                    return dryRunCandleFetcherProvider.get()
                }

                val influxDbConfig =
                    InfluxDbConfig(
                        url = options.influxDbUrl,
                        token = requireNotNull(options.influxDbToken) { "InfluxDB token is required." },
                        org = options.influxDbOrg,
                        bucket = options.influxDbBucket,
                    )

                val influxDbFactory = influxDbCandleFetcherFactoryProvider.get()
                return influxDbFactory.create(influxDbConfig)
            }
        }

    companion object {
        private const val DATABASE_USERNAME_ENV_VAR = "DATABASE_USERNAME"
        private const val DATABASE_PASSWORD_ENV_VAR = "DATABASE_PASSWORD"
        private const val INFLUXDB_TOKEN_ENV_VAR = "INFLUXDB_TOKEN"

        private fun getDatabaseUsername(options: StrategyDiscoveryPipelineOptions): String? =
            options.databaseUsername.takeIf { !it.isNullOrEmpty() }
                ?: System.getenv(DATABASE_USERNAME_ENV_VAR)

        private fun getDatabasePassword(options: StrategyDiscoveryPipelineOptions): String? =
            options.databasePassword.takeIf { !it.isNullOrEmpty() }
                ?: System.getenv(DATABASE_PASSWORD_ENV_VAR)

        private fun getInfluxDbToken(options: StrategyDiscoveryPipelineOptions): String? =
            options.influxDbToken.takeIf { !it.isNullOrEmpty() }
                ?: System.getenv(INFLUXDB_TOKEN_ENV_VAR)

        private fun getDiscoveryModule(options: StrategyDiscoveryPipelineOptions): Module =
            if (options.dryRun) DryRunDiscoveryModule() else DiscoveryModule()

        /**
         * Entry-point. Builds the injector, gets a factory instance,
         * creates a fully-configured [StrategyDiscoveryPipeline], and executes it.
         */
        @JvmStatic
        fun main(args: Array<String>) {
            // Set JVM flag for Jenetics RNG to work with both DirectRunner and FlinkRunner
            System.setProperty("io.jenetics.util.defaultRandomGenerator", "Random")
            PipelineOptionsFactory.register(StrategyDiscoveryPipelineOptions::class.java)
            val options =
                PipelineOptionsFactory
                    .fromArgs(*args)
                    .withValidation()
                    .`as`(StrategyDiscoveryPipelineOptions::class.java)

            options.isStreaming = !options.dryRun

            // Configure Flink-specific options for detached execution
            val flinkOptions = options.`as`(FlinkPipelineOptions::class.java)
            flinkOptions.setAttachedMode(options.dryRun)
            flinkOptions.setStreaming(options.isStreaming)

            // Override from environment variables if not set in args
            options.databaseUsername = getDatabaseUsername(options)
            options.databasePassword = getDatabasePassword(options)
            options.influxDbToken = getInfluxDbToken(options)

            val injector =
                Guice.createInjector(
                    BacktestingModule(),
                    getDiscoveryModule(options),
                    InfluxDbModule(),
                    MarketDataModule(),
                    PostgresModule(),
                    Ta4jModule.create(),
                )

            val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
            val components = factory.create(options)

            components.pipeline.run(options, components.candleFetcher)
        }
    }
}
