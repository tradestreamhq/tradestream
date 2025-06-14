package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Module
import com.verlumen.tradestream.backtesting.BacktestingModule
import com.verlumen.tradestream.influxdb.InfluxDbModule
import com.verlumen.tradestream.marketdata.MarketDataModule
import com.verlumen.tradestream.postgres.PostgresModule
import com.verlumen.tradestream.strategies.StrategiesModule
import com.verlumen.tradestream.ta4j.Ta4jModule
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
    companion object {
        private const val DATABASE_USERNAME_ENV_VAR = "DATABASE_USERNAME"
        private const val DATABASE_PASSWORD_ENV_VAR = "DATABASE_PASSWORD"

        private fun getDatabaseUsername(options: StrategyDiscoveryPipelineOptions): String? =
            options.databaseUsername.takeIf { !it.isNullOrEmpty() }
                ?: System.getenv(DATABASE_USERNAME_ENV_VAR)

        private fun getDatabasePassword(options: StrategyDiscoveryPipelineOptions): String? =
            options.databasePassword.takeIf { !it.isNullOrEmpty() }
                ?: System.getenv(DATABASE_PASSWORD_ENV_VAR)

        private fun getDiscoveryModule(options: StrategyDiscoveryPipelineOptions): Module {
            if (options.dryRun) {
                return DryRunDiscoveryModule()
            }
            return ProdDiscoveryModule()
        }

        /**
         * Entry-point. Builds the injector, gets a factory instance,
         * creates a fully-configured [StrategyDiscoveryPipeline], and executes it.
         */
        @JvmStatic
        fun main(args: Array<String>) {
            PipelineOptionsFactory.register(StrategyDiscoveryPipelineOptions::class.java)
            val options =
                PipelineOptionsFactory
                    .fromArgs(*args)
                    .withValidation()
                    .`as`(StrategyDiscoveryPipelineOptions::class.java)

            // Override from environment variables if not set in args
            options.databaseUsername = getDatabaseUsername(options)
            options.databasePassword = getDatabasePassword(options)

            val injector =
                Guice.createInjector(
                    BacktestingModule(),
                    InfluxDbModule(),
                    getDiscoveryModule(options),
                    MarketDataModule.create(),
                    PostgresModule(),
                    StrategiesModule(),
                    Ta4jModule.create(),
                )
            val pipeline = injector.getInstance(StrategyDiscoveryPipeline::class.java)

            pipeline.run(options)
        }
    }
}
