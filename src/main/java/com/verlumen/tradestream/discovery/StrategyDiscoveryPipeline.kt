package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo

/**
 * Builds and executes the strategy-discovery Beam pipeline.
 *
 * Flow:
 * 1. Read discovery requests from source (e.g., Kafka)
 * 2. Run GA optimization for each request
 * 3. Extract discovered strategies
 * 4. Persist strategies to PostgreSQL
 *
 * All transforms arrive through the factory pattern with Guice.
 */
class StrategyDiscoveryPipeline(
    private val discoveryRequestSource: DiscoveryRequestSource,
    private val runGAFn: RunGADiscoveryFn,
    private val extractFn: ExtractDiscoveredStrategiesFn,
    private val writeFn: WriteDiscoveredStrategiesToPostgresFn,
) {
    fun run() {
        val options = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java)
        options.isStreaming = true

        val pipeline = Pipeline.create(options)

        pipeline
            .apply("ReadDiscoveryRequests", discoveryRequestSource)
            .apply("RunGAStrategyDiscovery", ParDo.of(runGAFn))
            .apply("ExtractStrategies", ParDo.of(extractFn))
            .apply("WriteToPostgreSQL", ParDo.of(writeFn))

        pipeline.run().waitUntilFinish()
    }

    private fun createTestDiscoveryRequests(): List<KV<String, ByteArray>> {
        val now = System.currentTimeMillis()
        val startTime = Timestamps.fromMillis(now - 100000)
        val endTime = Timestamps.fromMillis(now)

        val requestProto =
            StrategyDiscoveryRequest
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

        return listOf(requestProto.toByteArray()))
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }
}
