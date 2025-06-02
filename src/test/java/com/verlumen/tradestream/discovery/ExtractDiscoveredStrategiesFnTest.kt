package com.verlumen.tradestream.discovery

import com.google.protobuf.Any
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.discovery.proto.Discovery.DiscoveredStrategy
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryResult
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class ExtractDiscoveredStrategiesFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Test
    fun testExtractMultipleStrategies() {
        val params1 = SmaRsiParameters.newBuilder().setRsiPeriod(10).build()
        val strategy1 =
            DiscoveredStrategy
                .newBuilder()
                .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).setParameters(Any.pack(params1)))
                .setScore(0.5)
                .setSymbol("BTC/USD")
                .setStartTime(Timestamps.fromMillis(1000L))
                .setEndTime(Timestamps.fromMillis(2000L))
                .build()

        val params2 = SmaRsiParameters.newBuilder().setRsiPeriod(20).build()
        val strategy2 =
            DiscoveredStrategy
                .newBuilder()
                .setStrategy(Strategy.newBuilder().setType(StrategyType.EMA_MACD).setParameters(Any.pack(params2)))
                .setScore(0.8)
                .setSymbol("ETH/USD")
                .setStartTime(Timestamps.fromMillis(3000L))
                .setEndTime(Timestamps.fromMillis(4000L))
                .build()

        val discoveryResult =
            StrategyDiscoveryResult
                .newBuilder()
                .addTopStrategies(strategy1)
                .addTopStrategies(strategy2)
                .build()

        val input: PCollection<StrategyDiscoveryResult> = pipeline.apply(Create.of(discoveryResult))
        val output: PCollection<DiscoveredStrategy> = input.apply(ParDo.of(ExtractDiscoveredStrategiesFn()))

        PAssert.that(output).containsInAnyOrder(strategy1, strategy2)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testExtractSingleStrategy() {
        val params1 = SmaRsiParameters.newBuilder().setRsiPeriod(10).build()
        val strategy1 =
            DiscoveredStrategy
                .newBuilder()
                .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).setParameters(Any.pack(params1)))
                .setScore(0.5)
                .build()

        val discoveryResult =
            StrategyDiscoveryResult
                .newBuilder()
                .addTopStrategies(strategy1)
                .build()

        val input: PCollection<StrategyDiscoveryResult> = pipeline.apply(Create.of(discoveryResult))
        val output: PCollection<DiscoveredStrategy> = input.apply(ParDo.of(ExtractDiscoveredStrategiesFn()))

        PAssert.that(output).containsInAnyOrder(strategy1)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testExtractEmptyResult() {
        val discoveryResult = StrategyDiscoveryResult.newBuilder().build() // No strategies

        val input: PCollection<StrategyDiscoveryResult> = pipeline.apply(Create.of(discoveryResult))
        val output: PCollection<DiscoveredStrategy> = input.apply(ParDo.of(ExtractDiscoveredStrategiesFn()))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testExtractFromNullElementInPCollection() {
        // Though PCollection<StrategyDiscoveryResult?> is not ideal,
        // testing DoFn's robustness to null elements if they manage to get in.
        // The DoFn's processElement expects a non-null `result`.
        // A Beam pipeline would typically filter nulls or use a Coder that doesn't allow them
        // for PCollection<StrategyDiscoveryResult>. This test assumes a PCollection<StrategyDiscoveryResult>
        // where an element might be null, and the DoFn should handle it.
        // The current DoFn's `result?` handles this.

        val nullResult: StrategyDiscoveryResult? = null
        val input: PCollection<StrategyDiscoveryResult?> = pipeline.apply(Create.of(nullResult))

        @Suppress("UNCHECKED_CAST")
        val castedInput = input as PCollection<StrategyDiscoveryResult>

        val output: PCollection<DiscoveredStrategy> = castedInput.apply(ParDo.of(ExtractDiscoveredStrategiesFn()))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}
