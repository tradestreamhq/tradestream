package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.Singleton
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.io.kafka.KafkaRecord
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.SerializableFunction
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
 * All DoFns and options arrive through Guice.
 */
@Singleton
class StrategyDiscoveryPipeline
    @Inject
    constructor(
        private val options: StrategyDiscoveryPipelineOptions,
        private val deserializeFn: DeserializeStrategyDiscoveryRequestFn,
        private val runGAFn: RunGADiscoveryFn,
        private val extractFn: ExtractDiscoveredStrategiesFn,
        private val writeFn: WriteDiscoveredStrategiesToPostgresFn,
    ) {
        fun run() {
            // Ensure streaming mode; useful if caller forgets --streaming=true
            options.isStreaming = true

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
                ).apply(
                    "ExtractKVFromRecord",
                    MapElements.via(
                        object : SerializableFunction<KafkaRecord<String, ByteArray>, KV<String, ByteArray>> {
                            override fun apply(input: KafkaRecord<String, ByteArray>): KV<String, ByteArray> = input.kv
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

            /**
             * Entry-point.  Builds the injector, gets **one** fully-wired instance of
             * [StrategyDiscoveryPipeline], and executes it.
             */
            @JvmStatic
            fun main(args: Array<String>) {
                val options =
                    PipelineOptionsFactory
                        .fromArgs(*args)
                        .withValidation()
                        .`as`(StrategyDiscoveryPipelineOptions::class.java)

                val injector = Guice.createInjector(DiscoveryModule(options))
                injector.getInstance(StrategyDiscoveryPipeline::class.java).run()
            }
        }
    }
