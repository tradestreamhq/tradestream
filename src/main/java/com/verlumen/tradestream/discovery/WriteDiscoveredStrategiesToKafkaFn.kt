package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.transforms.DoFn.Element
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.Setup
import org.apache.beam.sdk.transforms.DoFn.Teardown
import org.apache.kafka.clients.producer.KafkaProducer
import org.apache.kafka.clients.producer.ProducerConfig
import org.apache.kafka.clients.producer.ProducerRecord
import org.apache.kafka.common.serialization.ByteArraySerializer
import org.apache.kafka.common.serialization.StringSerializer
import java.io.Serializable
import java.util.Properties

/**
 * Kafka sink for writing discovered strategies to a Kafka topic.
 *
 * This implementation uses KafkaProducer to write strategies directly to Kafka,
 * providing reliable delivery with configurable reliability guarantees.
 */
class WriteDiscoveredStrategiesToKafkaFn
    @Inject
    constructor(
        @Assisted private val kafkaBootstrapServers: String,
        @Assisted private val topic: String,
    ) : DiscoveredStrategySink(),
        Serializable {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID: Long = 1L
        }

        @Transient
        private var kafkaProducer: KafkaProducer<String, ByteArray>? = null

        @Setup
        fun setup() {
            // Initialize Kafka producer with production-ready configuration
            val props =
                Properties().apply {
                    put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaBootstrapServers)
                    put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer::class.java.name)
                    put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, ByteArraySerializer::class.java.name)

                    // Reliability settings
                    put(ProducerConfig.ACKS_CONFIG, "1") // Wait for leader acknowledgment
                    put(ProducerConfig.RETRIES_CONFIG, 3)
                    put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true)

                    // Performance settings
                    put(ProducerConfig.BATCH_SIZE_CONFIG, 16384)
                    put(ProducerConfig.LINGER_MS_CONFIG, 5)
                    put(ProducerConfig.BUFFER_MEMORY_CONFIG, 33554432)

                    // Ordering guarantee
                    put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 1)
                }

            kafkaProducer = KafkaProducer(props)
            logger.atInfo().log("Kafka producer initialized for topic: %s", topic)
        }

        @ProcessElement
        fun processElement(
            @Element element: DiscoveredStrategy,
        ) {
            try {
                val producer =
                    requireNotNull(kafkaProducer) {
                        "Kafka producer not initialized. Setup method may not have been called."
                    }

                // Serialize the DiscoveredStrategy to bytes
                val messageBytes = element.toByteArray()

                // Use symbol as the key for partitioning (strategies for same symbol go to same partition)
                val key = element.symbol

                // Create producer record
                val record = ProducerRecord(topic, key, messageBytes)

                // Send and wait for completion (synchronous for reliability)
                val future = producer.send(record)
                val metadata = future.get() // This blocks until completion

                logger.atInfo().log(
                    "Successfully wrote strategy to Kafka topic '%s', partition %d, offset %d: symbol=%s, score=%f, type=%s",
                    metadata.topic(),
                    metadata.partition(),
                    metadata.offset(),
                    element.symbol,
                    element.score,
                    element.strategy.type,
                )
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log(
                    "Failed to write strategy to Kafka for symbol '%s'",
                    element.symbol,
                )
                throw e
            }
        }

        @Teardown
        fun teardown() {
            kafkaProducer?.close()
            logger.atInfo().log("Kafka producer closed")
        }
    }

/**
 * Factory for creating Kafka sink instances.
 */
interface WriteDiscoveredStrategiesToKafkaFactory {
    fun create(
        kafkaBootstrapServers: String,
        topic: String,
    ): WriteDiscoveredStrategiesToKafkaFn
}
