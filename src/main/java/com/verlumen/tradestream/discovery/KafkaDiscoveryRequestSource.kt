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
 * Kafka implementation of DiscoveryRequestSource that reads strategy discovery requests
 * from a Kafka topic and deserializes them into StrategyDiscoveryRequest objects.
 */
class KafkaDiscoveryRequestSource
    @Inject
    constructor(
        private val deserializeFn: DeserializeStrategyDiscoveryRequestFn,
        @Assisted private val options: StrategyDiscoveryPipelineOptions,
    ) : DiscoveryRequestSource() {
        override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> =
            input.pipeline
                .apply(
                    "ReadDiscoveryRequestsFromKafka",
                    KafkaIO
                        .read<String, ByteArray>()
                        .withBootstrapServers(options.kafkaBootstrapServers)
                        .withTopic(options.strategyDiscoveryRequestTopic)
                        .withKeyDeserializer(StringDeserializer::class.java)
                        .withValueDeserializer(ByteArrayDeserializer::class.java),
                ).apply(
                    "ExtractKVFromRecord",
                    MapElements.via(
                        object : SimpleFunction<KafkaRecord<String, ByteArray>, KV<String, ByteArray>>() {
                            override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> = input.kv
                        },
                    ),
                ).apply("DeserializeProtoRequests", ParDo.of(deserializeFn))
    }
