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
        override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> {
            var kafkaRead =
                KafkaIO
                    .read<String, ByteArray>()
                    .withBootstrapServers(options.kafkaBootstrapServers)
                    .withTopic(options.strategyDiscoveryRequestTopic)
                    .withKeyDeserializer(StringDeserializer::class.java)
                    .withValueDeserializer(ByteArrayDeserializer::class.java)

            // Apply security settings from environment variables
            val securityProtocol = System.getenv("KAFKA_SECURITY_PROTOCOL")
            if (!securityProtocol.isNullOrEmpty()) {
                kafkaRead = kafkaRead.updateConsumerProperties(
                    mapOf("security.protocol" to securityProtocol) as Map<String, Any>
                )
            }
            val saslMechanism = System.getenv("KAFKA_SASL_MECHANISM")
            if (!saslMechanism.isNullOrEmpty()) {
                kafkaRead = kafkaRead.updateConsumerProperties(
                    mapOf("sasl.mechanism" to saslMechanism) as Map<String, Any>
                )
            }
            val saslJaasConfig = System.getenv("KAFKA_SASL_JAAS_CONFIG")
            if (!saslJaasConfig.isNullOrEmpty()) {
                kafkaRead = kafkaRead.updateConsumerProperties(
                    mapOf("sasl.jaas.config" to saslJaasConfig) as Map<String, Any>
                )
            }

            return input.pipeline
                .apply(
                    "ReadDiscoveryRequestsFromKafka",
                    kafkaRead,
                ).apply(
                    "ExtractKVFromRecord",
                    MapElements.via(
                        object : SimpleFunction<KafkaRecord<String, ByteArray>, KV<String, ByteArray>>() {
                            override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> = input.kv
                        },
                    ),
                ).apply("DeserializeProtoRequests", ParDo.of(deserializeFn))
        }
    }
