package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.verlumen.tradestream.postgres.PostgresModule
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
        /**
         * Entry-point. Builds the injector, gets a factory instance,
         * creates a fully-configured [StrategyDiscoveryPipeline], and executes it.
         */
        @JvmStatic
        fun main(args: Array<String>) {
            val options =
                PipelineOptionsFactory
                    .fromArgs(*args)
                    .withValidation()
                    .`as`(StrategyDiscoveryPipelineOptions::class.java)

            val injector =
                Guice.createInjector(
                    DiscoveryModule(),
                    PostgresModule(),
                )
            val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)

            factory.create(options).run()
        }
    }
}
