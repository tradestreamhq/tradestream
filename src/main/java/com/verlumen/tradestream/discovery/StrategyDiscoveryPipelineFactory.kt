package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.Singleton

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
        private val deserializeFn: DeserializeStrategyDiscoveryRequestFn,
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val writeFn: WriteDiscoveredStrategiesToPostgresFn,
    ) : StrategyDiscoveryPipelineFactory {
    
    override fun create(options: StrategyDiscoveryPipelineOptions): StrategyDiscoveryPipeline {
        return StrategyDiscoveryPipeline(
            kafkaBootstrapServers = options.kafkaBootstrapServers,
            strategyDiscoveryRequestTopic = options.strategyDiscoveryRequestTopic,
            isStreaming = true, // Default to streaming mode
            deserializeFn = deserializeFn,
            runGAFn = runGAFn,
            extractFn = extractFn,
            writeFn = writeFn,
        )
    }
}
