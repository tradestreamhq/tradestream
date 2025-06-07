package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Guice
import com.google.inject.Injector
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.ParDo
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer

/**
 * Main pipeline for discovering trading strategies using genetic algorithms.
 *
 * Flow:
 * 1. Read strategy discovery requests from Kafka
 * 2. Deserialize protobuf messages
 * 3. Run GA optimization for each request
 * 4. Extract discovered strategies from results
 * 5. Write strategies to PostgreSQL database
 *
 * All transforms are created via Guice dependency injection.
 */
object StrategyDiscoveryPipeline {
    private val logger = FluentLogger.forEnclosingClass()

    @JvmStatic
    fun main(args: Array<String>) {
        val options =
            PipelineOptionsFactory
                .fromArgs(*args)
                .withValidation()
                .`as`(StrategyDiscoveryPipelineOptions::class.java)

        options.isStreaming = true

        // Create Guice injector with modules
        val injector = createInjector(options)

        val pipeline = Pipeline.create(options)

        pipeline
            .apply(
                "ReadDiscoveryRequestsFromKafka",
                KafkaIO
                    .read<String, ByteArray>()
                    .withBootstrapServers(options.kafkaBootstrapServers)
                    .withTopic(options.strategyDiscoveryRequestTopic)
                    .withKeyDeserializer(StringDeserializer::class.java)
                    .withValueDeserializer(ByteArrayDeserializer::class.java),
            ).apply("DeserializeProtoRequests", ParDo.of(injector.getInstance(DeserializeStrategyDiscoveryRequestFn::class.java)))
            .apply("RunGAStrategyDiscovery", ParDo.of(injector.getInstance(RunGADiscoveryFn::class.java)))
            .apply("ExtractDiscoveredStrategies", ParDo.of(injector.getInstance(ExtractDiscoveredStrategiesFn::class.java)))
            .apply("WriteToPostgreSQL", ParDo.of(injector.getInstance(WriteDiscoveredStrategiesToPostgresFn::class.java)))

        pipeline.run().waitUntilFinish()
    }

    private fun createInjector(options: StrategyDiscoveryPipelineOptions): Injector =
        Guice.createInjector(DiscoveryModule(options))
}
