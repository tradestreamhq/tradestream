package com.verlumen.tradestream.discovery

import com.google.inject.Inject

/**
 * Kafka implementation of DiscoveryRequestSourceFactory that creates KafkaDiscoveryRequestSource
 * instances configured with Kafka connection parameters from pipeline options.
 */
class KafkaDiscoveryRequestSourceFactory @Inject constructor(
    private val deserializeFn: DeserializeStrategyDiscoveryRequestFn
) : DiscoveryRequestSourceFactory {

    override fun create(options: StrategyDiscoveryPipelineOptions): DiscoveryRequestSource {
        return KafkaDiscoveryRequestSource(
            deserializeFn,
            options.kafkaBootstrapServers,
            options.strategyDiscoveryRequestTopic
        )
    }
}
