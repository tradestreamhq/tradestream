package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.MockitoAnnotations

@RunWith(JUnit4::class)
class DeserializeStrategyDiscoveryRequestFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    // The class under test - will be injected by Guice
    @Inject
    lateinit var deserializeStrategyDiscoveryRequestFn: DeserializeStrategyDiscoveryRequestFn

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        // Create Guice injector with BoundFieldModule to inject the test fixture
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)
    }

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

        val output: PCollection<StrategyDiscoveryRequest> = input.apply(ParDo.of(deserializeStrategyDiscoveryRequestFn))

        PAssert.that(output).containsInAnyOrder(requestProto)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testInvalidDeserialization() {
        val invalidBytes = "not-a-proto".toByteArray()
        val input: PCollection<KV<String, ByteArray>> = pipeline.apply(Create.of(KV.of("key2", invalidBytes)))

        val output: PCollection<StrategyDiscoveryRequest> = input.apply(ParDo.of(deserializeStrategyDiscoveryRequestFn))

        PAssert.that(output).empty() // Expect no output for invalid proto
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testNullValue() {
        val input: PCollection<KV<String, ByteArray?>> = pipeline.apply(Create.of(KV.of<String, ByteArray?>("key3", null)))

        @Suppress("UNCHECKED_CAST")
        val castedInput = input as PCollection<KV<String, ByteArray>>

        val output: PCollection<StrategyDiscoveryRequest> = castedInput.apply(ParDo.of(deserializeStrategyDiscoveryRequestFn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}
