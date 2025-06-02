package com.verlumen.tradestream.discovery

import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.discovery.proto.Discovery.GAConfig
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryRequest
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class DeserializeStrategyDiscoveryRequestFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Test
    fun testValidDeserialization() {
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

        val serializedRequest = requestProto.toByteArray()
        val input: PCollection<KV<String, ByteArray>> = pipeline.apply(Create.of(KV.of("key1", serializedRequest)))

        val output: PCollection<StrategyDiscoveryRequest> = input.apply(ParDo.of(DeserializeStrategyDiscoveryRequestFn()))

        PAssert.that(output).containsInAnyOrder(requestProto)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testInvalidDeserialization() {
        val invalidBytes = "not-a-proto".toByteArray()
        val input: PCollection<KV<String, ByteArray>> = pipeline.apply(Create.of(KV.of("key2", invalidBytes)))

        val output: PCollection<StrategyDiscoveryRequest> = input.apply(ParDo.of(DeserializeStrategyDiscoveryRequestFn()))

        PAssert.that(output).empty() // Expect no output for invalid proto
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testNullValue() {
        val input: PCollection<KV<String, ByteArray?>> = pipeline.apply(Create.of(KV.of<String, ByteArray?>("key3", null)))

        // The DoFn expects KV<String, ByteArray>, so we need to handle the nullable ByteArray scenario or filter it before.
        // For this test, assuming the DoFn's internal null check on context.element().value is sufficient.
        @Suppress("UNCHECKED_CAST")
        val castedInput = input as PCollection<KV<String, ByteArray>>

        val output: PCollection<StrategyDiscoveryRequest> = castedInput.apply(ParDo.of(DeserializeStrategyDiscoveryRequestFn()))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}
