package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.verlumen.tradestream.execution.RunMode
import com.verlumen.tradestream.kafka.KafkaConsumerFactory
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PInput
import org.apache.kafka.common.serialization.StringDeserializer

/**
 * A Kafka-based implementation of DiscoveryRequestSource that reads strategy discovery requests
 * from a Kafka topic.
 */
class KafkaDiscoveryRequestSource
    @AssistedInject
    constructor(
        @Assisted private val runMode: RunMode,
        private val kafkaConsumerFactory: KafkaConsumerFactory,
    ) : DiscoveryRequestSource {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val DISCOVERY_REQUESTS_TOPIC = "strategy-discovery-requests"
        }

        override fun expand(input: PInput): PCollection<StrategyDiscoveryRequest> {
            logger.atInfo().log("Reading discovery requests from Kafka topic: $DISCOVERY_REQUESTS_TOPIC")

            return input.pipeline.apply(
                KafkaIO
                    .read<String, String>()
                    .withBootstrapServers(kafkaConsumerFactory.bootstrapServers)
                    .withTopic(DISCOVERY_REQUESTS_TOPIC)
                    .withKeyDeserializer(StringDeserializer::class.java)
                    .withValueDeserializer(StringDeserializer::class.java)
                    .withConsumerFactoryFn { kafkaConsumerFactory.createConsumer() }
                    .withoutMetadata()
                    .apply("ParseDiscoveryRequests", ParseDiscoveryRequests()),
            )
        }
    }
