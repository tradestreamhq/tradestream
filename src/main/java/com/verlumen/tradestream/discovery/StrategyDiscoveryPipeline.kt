package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.verlumen.tradestream.execution.RunMode
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.transforms.ParDo

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
class StrategyDiscoveryPipeline
    @AssistedInject
    constructor(
        @Assisted private val pipeline: Pipeline,
        @Assisted private val runMode: RunMode,
        private val discoveryRequestSource: DiscoveryRequestSource,
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val discoveredStrategySink: DiscoveredStrategySink,
    ) {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }

        fun run() {
            logger.atInfo().log("Starting strategy discovery pipeline in ${runMode.name} mode")

            pipeline
                .apply("ReadDiscoveryRequests", discoveryRequestSource)
                .apply("RunGAStrategyDiscovery", ParDo.of(runGAFn))
                .apply("ExtractStrategies", ParDo.of(extractFn))
                .apply("WriteStrategies", discoveredStrategySink)

            pipeline.run().waitUntilFinish()

            logger.atInfo().log("Strategy discovery pipeline completed")
        }
    }
