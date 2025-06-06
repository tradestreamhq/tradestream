package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.marketdata.CandleFetcher
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.StrategyType
import io.jenetics.DoubleChromosome
import io.jenetics.DoubleGene
import io.jenetics.Genotype
import io.jenetics.engine.Engine
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.eq
import org.mockito.kotlin.whenever
import java.io.Serializable

// Create a serializable factory for test engines
class SerializableTestEngineFactory : Serializable {
    companion object {
        private const val serialVersionUID = 1L
        
        fun createSuccessEngine(): Engine<DoubleGene, Double> =
            Engine
                .builder(
                    { genotype: Genotype<DoubleGene> -> genotype.chromosome().get(0).allele() * 1.0 },
                    Genotype.of(DoubleChromosome.of(0.0, 1.0, 1)),
                ).populationSize(5)
                .build()

        fun createEmptyResultEngine(): Engine<DoubleGene, Double> =
            Engine
                .builder(
                    { _: Genotype<DoubleGene> -> 0.0 },
                    Genotype.of(DoubleChromosome.of(0.0, 1.0, 1)),
                ).populationSize(1)
                .build()
    }
}

@RunWith(JUnit4::class)
class RunGADiscoveryFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    @Bind
    @Mock(serializable = true)
    lateinit var mockCandleFetcher: CandleFetcher

    @Bind
    @Mock(serializable = true)
    lateinit var mockGaEngineFactory: GAEngineFactory

    @Bind
    @Mock(serializable = true)
    lateinit var mockGenotypeConverter: GenotypeConverter

    @Inject
    lateinit var runGADiscoveryFn: RunGADiscoveryFn

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)
    }

    private fun createTestRequest(): StrategyDiscoveryRequest {
        val now = System.currentTimeMillis()
        return StrategyDiscoveryRequest
            .newBuilder()
            .setSymbol("BTC/USD")
            .setStartTime(Timestamps.fromMillis(now - 200000))
            .setEndTime(Timestamps.fromMillis(now - 100000))
            .setStrategyType(StrategyType.SMA_RSI)
            .setTopN(1)
            .setGaConfig(
                GAConfig
                    .newBuilder()
                    .setMaxGenerations(10)
                    .setPopulationSize(20)
                    .build(),
            ).build()
    }

    private fun createDummyCandle(timestamp: Timestamp): Candle =
        Candle
            .newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair("BTC/USD")
            .setOpen(100.0)
            .setHigh(110.0)
            .setLow(90.0)
            .setClose(105.0)
            .setVolume(1000.0)
            .build()

    @Test
    fun testRunGADiscoveryFn_success() {
        val request = createTestRequest()
        val dummyCandle = createDummyCandle(request.startTime)
        val candles = ImmutableList.of(dummyCandle)

        val smaRsiParams =
            SmaRsiParameters
                .newBuilder()
                .setMovingAveragePeriod(10)
                .setRsiPeriod(14)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build()
        val paramsAny = Any.pack(smaRsiParams)

        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(candles)
        
        whenever(mockGaEngineFactory.createEngine(any<GAEngineParams>()))
            .thenAnswer { SerializableTestEngineFactory.createSuccessEngine() }

        whenever(
            mockGenotypeConverter.convertToParameters(any(), eq(StrategyType.SMA_RSI)),
        ).thenReturn(paramsAny)

        val input: PCollection<StrategyDiscoveryRequest> =
            pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        PAssert.that(output).satisfies { results ->
            val resultList = results.toList()
            assert(resultList.size == 1) { "Expected 1 result, got ${resultList.size}" }
            val result = resultList[0]
            assert(result.topStrategiesCount == 1) { "Expected 1 strategy, got ${result.topStrategiesCount}" }
            val strategy = result.getTopStrategies(0)
            assert(strategy.symbol == "BTC/USD") { "Expected BTC/USD, got ${strategy.symbol}" }
            assert(strategy.strategy.type == StrategyType.SMA_RSI) { "Expected SMA_RSI type" }
            assert(strategy.score >= 0) { "Expected non-negative score, got ${strategy.score}" }
            null
        }
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testRunGADiscoveryFn_noCandles() {
        val request = createTestRequest()
        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(ImmutableList.of())

        val input: PCollection<StrategyDiscoveryRequest> =
            pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testRunGADiscoveryFn_gaYieldsNoResults() {
        val requestOriginal = createTestRequest()
        val request = requestOriginal.toBuilder().setTopN(0).build()

        val dummyCandle = createDummyCandle(request.startTime)
        val candles = ImmutableList.of(dummyCandle)

        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(candles)
        
        whenever(mockGaEngineFactory.createEngine(any<GAEngineParams>()))
            .thenAnswer { SerializableTestEngineFactory.createEmptyResultEngine() }

        val input: PCollection<StrategyDiscoveryRequest> =
            pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}
