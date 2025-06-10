package com.verlumen.tradestream.discovery

import com.google.inject.Inject

/**
 * Factory interface for creating DiscoveryRequestSource instances with runtime configuration.
 * This follows the same pattern as WriteDiscoveredStrategiesToPostgresFnFactory.
 */
interface DiscoveryRequestSourceFactory {
    /**
     * Creates a DiscoveryRequestSource configured with the given pipeline options.
     */
    fun create(options: StrategyDiscoveryPipelineOptions): DiscoveryRequestSource
}

/**
 * Implementation of DiscoveryRequestSourceFactory that creates KafkaDiscoveryRequestSource
 * instances configured with Kafka connection parameters from pipeline options.
 */
class DiscoveryRequestSourceFactoryImpl @Inject constructor(
    private val kafkaDiscoveryRequestSourceFactory: KafkaDiscoveryRequestSourceFactory
) : DiscoveryRequestSourceFactory {

    override fun create(options: StrategyDiscoveryPipelineOptions): DiscoveryRequestSource {
        return kafkaDiscoveryRequestSourceFactory.create(
            options.kafkaBootstrapServers,
            options.strategyDiscoveryRequestTopic
        )
    }
}

/**
 * Assisted injection factory for creating KafkaDiscoveryRequestSource instances
 * with runtime configuration parameters.
 */
interface KafkaDiscoveryRequestSourceFactory {
    fun create(kafkaBootstrapServers: String, strategyDiscoveryRequestTopic: String): KafkaDiscoveryRequestSource
}
