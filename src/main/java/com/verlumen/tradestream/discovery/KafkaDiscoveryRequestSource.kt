package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.google.protobuf.util.JsonFormat
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.ProcessContext
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import org.apache.kafka.common.serialization.StringDeserializer

/**
 * A source that reads strategy discovery requests from Kafka.
 */
class KafkaDiscoveryRequestSource
    @AssistedInject
    constructor(
        @Assisted private val bootstrapServers: String,
        @Assisted private val topic: String,
        @Assisted private val groupId: String,
    ) : PTransform<PBegin, PCollection<StrategyDiscoveryRequest>>(),
        DiscoveryRequestSource {
        override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> =
            input
                .apply(
                    KafkaIO
                        .read<String, String>()
                        .withBootstrapServers(bootstrapServers)
                        .withTopic(topic)
                        .withKeyDeserializer(StringDeserializer::class.java)
                        .withValueDeserializer(StringDeserializer::class.java)
                        .withConsumerConfigUpdates(
                            mapOf(
                                "group.id" to groupId,
                                "auto.offset.reset" to "latest",
                            ),
                        ).withoutMetadata(),
                ).apply(
                    ParDo.of(
                        object : DoFn<KV<String, String>, StrategyDiscoveryRequest>() {
                            @ProcessElement
                            fun processElement(c: ProcessContext) {
                                val json = c.element().value
                                try {
                                    val request = StrategyDiscoveryRequest.newBuilder()
                                    JsonFormat.parser().merge(json, request)
                                    c.output(request.build())
                                } catch (e: Exception) {
                                    logger.atWarning().withCause(e).log("Failed to parse discovery request: $json")
                                }
                            }
                        },
                    ),
                )

        /**
         * Factory interface for assisted injection
         */
        interface Factory {
            fun create(
                bootstrapServers: String,
                topic: String,
                groupId: String,
            ): KafkaDiscoveryRequestSource
        }

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }
    }
