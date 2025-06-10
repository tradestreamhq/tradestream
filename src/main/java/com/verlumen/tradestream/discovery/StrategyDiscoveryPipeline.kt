package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.io.kafka.KafkaRecord
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.Create
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

        val input = if (options.dryRun) {
            pipeline.apply(
                "CreateTestData",
                Create.of(createTestDiscoveryRequests())
            )
        } else {
            pipeline.apply(
                "ReadDiscoveryRequestsFromKafka",
                KafkaIO
                    .read<String, ByteArray>()
                    .withBootstrapServers(kafkaBootstrapServers)
                    .withTopic(strategyDiscoveryRequestTopic)
                    .withKeyDeserializer(StringDeserializer::class.java)
                    .withValueDeserializer(ByteArrayDeserializer::class.java),
            ).apply(
                "ExtractKVFromRecord",
                MapElements.via(
                    object : SimpleFunction<KafkaRecord<String, ByteArray>, KV<String, ByteArray>>() {
                        override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> = input.kv
                    },
                ),
            )
        }

        input
            .apply("DeserializeProtoRequests", ParDo.of(deserializeFn))
            .apply("RunGAStrategyDiscovery", ParDo.of(runGAFn))
            .apply("ExtractStrategies", ParDo.of(extractFn))
            .apply("WriteToPostgreSQL", ParDo.of(writeFn))

        pipeline.run().waitUntilFinish()
    }

    private fun createTestDiscoveryRequests(): List<KV<String, ByteArray>> {
        val now = System.currentTimeMillis()
        val startTime = Timestamps.fromMillis(now - 100000)
        val endTime = Timestamps.fromMillis(now)

        val requestProto = StrategyDiscoveryRequest
            .newBuilder()
            .setSymbol("BTC/USD")
            .setStartTime(startTime)
            .setEndTime(endTime)
            .setStrategyType(StrategyType.SMA_RSI)
            .setTopN(10)
            .setGaConfig(
                GAConfig
                    .newBuilder()
                    .setMaxGenerations(50)
                    .setPopulationSize(100)
                    .build(),
            ).build()

        return listOf(KV.of("test-key", requestProto.toByteArray()))
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }
}
