// src/main/java/com/verlumen/tradestream/discovery/KafkaDiscoveryRequestSource.kt
package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.io.kafka.KafkaRecord
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SimpleFunction
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer

/**
 * Kafka implementation of DiscoveryRequestSource that reads strategy discovery
 * requests from a Kafka topic and deserializes them.
 *
 * This implementation encapsulates:
 * 1. Reading from Kafka
 * 2. Extracting key-value pairs from Kafka records
 * 3. Deserializing protobuf messages to StrategyDiscoveryRequest objects
 *
 * Configuration is provided through assisted injection.
 */
class KafkaDiscoveryRequestSource @Inject constructor(
    private val deserializeFn: DeserializeStrategyDiscoveryRequestFn,
    @Assisted private val kafkaBootstrapServers: String,
    @Assisted private val strategyDiscoveryRequestTopic: String
) : DiscoveryRequestSource() {

    companion object {
        private const val serialVersionUID = 1L
    }

    override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> {
        return input.pipeline
            .apply(
                "ReadDiscoveryRequestsFromKafka",
                KafkaIO
                    .read<String, ByteArray>()
                    .withBootstrapServers(kafkaBootstrapServers)
                    .withTopic(strategyDiscoveryRequestTopic)
                    .withKeyDeserializer(StringDeserializer::class.java)
                    .withValueDeserializer(ByteArrayDeserializer::class.java),
            )
            .apply(
                "ExtractKVFromRecord",
                MapElements.via(
                    object : SimpleFunction<KafkaRecord<String, ByteArray>, KV<String, ByteArray>>() {
                        override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> = input.kv
                    },
                ),
            )
            .apply("DeserializeProtoRequests", ParDo.of(deserializeFn))
    }
}
