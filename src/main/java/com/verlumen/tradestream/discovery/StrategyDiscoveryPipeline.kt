package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.io.kafka.KafkaRecord
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SimpleFunction
import org.apache.beam.sdk.values.KV
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer

/**
 * Builds and executes the strategy-discovery Beam pipeline.
 *
 * Flow:
 * 1. Read discovery requests from Kafka
 * 2. Deserialize protobuf messages
 * 3. Run GA optimisation for each request
 * 4. Extract discovered strategies
 * 5. Persist strategies to PostgreSQL
 *
 * All DoFns arrive through the factory pattern with Guice.
 */
class StrategyDiscoveryPipeline(
    private val kafkaBootstrapServers: String,
    private val strategyDiscoveryRequestTopic: String,
    private val isStreaming: Boolean,
    private val deserializeFn: DeserializeStrategyDiscoveryRequestFn,
    private val runGAFn: RunGADiscoveryFn,
    private val extractFn: ExtractDiscoveredStrategiesFn,
    private val writeFn: WriteDiscoveredStrategiesToPostgresFn,
) {
    fun run() {
        val options = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java)
        // Ensure streaming mode; useful if caller forgets --streaming=true
        options.isStreaming = isStreaming

        val pipeline = Pipeline.create(options)

        pipeline
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
                        override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> =
                            input.kv
                    },
                ),
            ).apply("DeserializeProtoRequests", ParDo.of(deserializeFn))
            .apply("RunGAStrategyDiscovery", ParDo.of(runGAFn))
            .apply("ExtractStrategies", ParDo.of(extractFn))
            .apply("WriteToPostgreSQL", ParDo.of(writeFn))

        pipeline.run().waitUntilFinish()
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }
}
