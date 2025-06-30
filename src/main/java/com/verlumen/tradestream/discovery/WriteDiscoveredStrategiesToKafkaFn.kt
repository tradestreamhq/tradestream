package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.transforms.DoFn.Element
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import java.io.Serializable

/**
 * Kafka sink for writing discovered strategies to a Kafka topic.
 *
 * This approach provides better decoupling and allows for:
 * - Asynchronous processing of discovered strategies
 * - Multiple consumers (e.g., PostgreSQL writer, analytics, etc.)
 * - Better fault tolerance and replay capabilities
 * - Easier testing and development
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

        @ProcessElement
        fun processElement(
            @Element element: DiscoveredStrategy,
        ) {
            try {
                // For now, just log the strategies that would be written to Kafka
                // In a full implementation, we would write to Kafka here
                logger.atInfo().log(
                    "Would write strategy to Kafka topic '%s': symbol=%s, score=%f, type=%s",
                    topic,
                    element.symbol,
                    element.score,
                    element.strategy.type,
                )
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Failed to process strategy for symbol '%s'", element.symbol)
                throw e
            }
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
