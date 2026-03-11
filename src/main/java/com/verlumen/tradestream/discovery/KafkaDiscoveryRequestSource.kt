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
        private fun buildSslConsumerConfig(): Map<String, Any> {
            val config = mutableMapOf<String, Any>()
            val securityProtocol = System.getenv("KAFKA_SECURITY_PROTOCOL") ?: "SSL"
            config["security.protocol"] = securityProtocol
            if (securityProtocol == "SSL" || securityProtocol == "SASL_SSL") {
                System.getenv("KAFKA_SSL_TRUSTSTORE_LOCATION")?.takeIf { it.isNotEmpty() }?.let {
                    config["ssl.truststore.location"] = it
                }
                System.getenv("KAFKA_SSL_TRUSTSTORE_PASSWORD")?.takeIf { it.isNotEmpty() }?.let {
                    config["ssl.truststore.password"] = it
                }
                System.getenv("KAFKA_SSL_KEYSTORE_LOCATION")?.takeIf { it.isNotEmpty() }?.let {
                    config["ssl.keystore.location"] = it
                }
                System.getenv("KAFKA_SSL_KEYSTORE_PASSWORD")?.takeIf { it.isNotEmpty() }?.let {
                    config["ssl.keystore.password"] = it
                }
                System.getenv("KAFKA_SSL_KEY_PASSWORD")?.takeIf { it.isNotEmpty() }?.let {
                    config["ssl.key.password"] = it
                }
            }
            return config
        }

        override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> =
            input.pipeline
                .apply(
                    "ReadDiscoveryRequestsFromKafka",
                    KafkaIO
                        .read<String, ByteArray>()
                        .withBootstrapServers(options.kafkaBootstrapServers)
                        .withTopic(options.strategyDiscoveryRequestTopic)
                        .withKeyDeserializer(StringDeserializer::class.java)
                        .withValueDeserializer(ByteArrayDeserializer::class.java)
                        .withConsumerConfigUpdates(buildSslConsumerConfig()),
                ).apply(
                    "ExtractKVFromRecord",
                    MapElements.via(
                        object : SimpleFunction<KafkaRecord<String, ByteArray>, KV<String, ByteArray>>() {
                            override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> = input.kv
                        },
                    ),
                ).apply("DeserializeProtoRequests", ParDo.of(deserializeFn))
    }
