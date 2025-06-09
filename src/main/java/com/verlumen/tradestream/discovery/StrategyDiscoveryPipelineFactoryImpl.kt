package com.verlumen.tradestream.discovery

import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.verlumen.tradestream.execution.RunMode
import org.apache.beam.sdk.Pipeline

class StrategyDiscoveryPipelineFactoryImpl
    @AssistedInject
    constructor(
        @Assisted private val pipeline: Pipeline,
        @Assisted private val runMode: RunMode,
        private val discoveryRequestSource: DiscoveryRequestSource,
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val discoveredStrategySink: DiscoveredStrategySink,
    ) : StrategyDiscoveryPipelineFactory {
        override fun create(): StrategyDiscoveryPipeline =
            StrategyDiscoveryPipeline(
                pipeline = pipeline,
                runMode = runMode,
                discoveryRequestSource = discoveryRequestSource,
                runGAFn = runGAFn,
                extractFn = extractFn,
                discoveredStrategySink = discoveredStrategySink,
            )
    } 
