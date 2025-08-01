package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.marketdata.CandleFetcher
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.transforms.ParDo

/**
 * Builds and executes the strategy-discovery Beam pipeline.
 *
 * Flow:
 * 1. Read discovery requests from source (e.g., Kafka)
 * 2. Run GA optimization for each request
 * 3. Extract discovered strategies
 * 4. Write strategies to Kafka topic
 *
 * All transforms arrive through the factory pattern with Guice.
 */
class StrategyDiscoveryPipeline
    @Inject
    constructor(
        private val runGADiscoveryFnFactory: RunGADiscoveryFnFactory,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val sinkFactory: DiscoveredStrategySinkFactory,
        private val discoveryRequestSourceFactory: DiscoveryRequestSourceFactory,
    ) {
        fun run(
            options: StrategyDiscoveryPipelineOptions,
            candleFetcher: CandleFetcher,
        ) {
            val discoveryRequestSource = discoveryRequestSourceFactory.create(options)
            val runGaFn = runGADiscoveryFnFactory.create(candleFetcher)

            // Create appropriate sink based on dry-run mode
            val sinkParams =
                if (options.dryRun) {
                    DiscoveredStrategySinkParams.DryRun
                } else {
                    val kafkaTopic = "discovered-strategies"
                    DiscoveredStrategySinkParams.Kafka(options.kafkaBootstrapServers, kafkaTopic)
                }
            val sink = sinkFactory.create(sinkParams)

            val pipeline = Pipeline.create(options)

            pipeline
                .apply("ReadDiscoveryRequests", discoveryRequestSource)
                .apply("RunGAStrategyDiscovery", ParDo.of(runGaFn))
                .apply("ExtractStrategies", ParDo.of(extractFn))
                .apply("WriteToKafka", ParDo.of(sink))

            // For detached execution, just run the pipeline without waiting
            pipeline.run()
        }

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }
    }
